using System.Net;
using Microsoft.Extensions.Options;

namespace ApiGateway.Services;

/// <summary>
/// Typed client for the Python analysis service.
///
/// Two things this deliberately does not do:
///
/// 1. It never lets a caller set the upstream API key. The
///    key is attached from server-side configuration on every
///    request, so no request body, query string or header from
///    the browser can influence or override it.
/// 2. It does not translate upstream error bodies. A status
///    code and the service's own JSON detail are passed
///    through, so a client sees exactly what the analysis
///    engine said.
/// </summary>
public sealed class PythonAnalysisClient
{
    private readonly HttpClient _client;
    private readonly PythonServiceOptions _options;
    private readonly ILogger<PythonAnalysisClient> _logger;

    public PythonAnalysisClient(
        HttpClient client,
        IOptions<PythonServiceOptions> options,
        ILogger<PythonAnalysisClient> logger)
    {
        _client = client;
        _options = options.Value;
        _logger = logger;

        _client.Timeout = TimeSpan.FromSeconds(
            _options.TimeoutSeconds);

        _client.DefaultRequestHeaders.Remove(
            _options.ApiKeyHeader);

        _client.DefaultRequestHeaders.Add(
            _options.ApiKeyHeader,
            _options.ApiKey);
    }

    public bool IsConfigured =>
        !string.IsNullOrWhiteSpace(_options.ApiKey);

    public async Task<UpstreamResponse> SendAsync(
        HttpMethod method,
        string path,
        object? body = null,
        CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(
            method,
            path);

        if (body is not null)
        {
            request.Content = JsonContent.Create(body);
        }

        return await SendAsync(
            request,
            cancellationToken);
    }

    /// <summary>
    /// Proxy a request verbatim, including its body and
    /// content type.
    ///
    /// Uploads must not be buffered into a strongly typed
    /// model: the Python service decides which fields matter,
    /// and re-declaring them here would mean two definitions
    /// of one contract that can drift apart.
    /// </summary>
    public async Task<UpstreamResponse> ForwardAsync(
        HttpMethod method,
        string path,
        HttpContent? content,
        CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(
            method,
            path)
        {
            Content = content,
        };

        return await SendAsync(
            request,
            cancellationToken);
    }

    private async Task<UpstreamResponse> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        try
        {
            using var response = await _client.SendAsync(
                request,
                cancellationToken);

            var payload = await response.Content
                .ReadAsStringAsync(cancellationToken);

            return new UpstreamResponse(
                (int)response.StatusCode,
                IsJson(response)
                    ? payload
                    : null,
                IsJson(response) ? null : payload,
                response.IsSuccessStatusCode);
        }
        catch (TaskCanceledException) when (
            !cancellationToken.IsCancellationRequested)
        {
            // Distinguishing a timeout from a client abort
            // matters: a timeout is a server-side problem the
            // caller cannot fix, and reporting it as a generic
            // 504 says so.
            _logger.LogError(
                "The Python service did not respond within {Timeout}s.",
                _options.TimeoutSeconds);

            return UpstreamResponse.GatewayTimeout(
                "The analysis service did not respond in "
                + "time. The question may still be "
                + "running; try again.");
        }
        catch (HttpRequestException exception)
        {
            _logger.LogError(
                exception,
                "Could not reach the Python service at {BaseUrl}.",
                _options.BaseUrl);

            return UpstreamResponse.BadGateway(
                "The analysis service is not reachable.");
        }
    }

    private static bool IsJson(HttpResponseMessage response) =>
        response.Content.Headers.ContentType
            ?.MediaType
            ?.Contains("json",
                StringComparison.OrdinalIgnoreCase)
        ?? false;
}

public static class JsonContent
{
    public static HttpContent Create(object body) =>
        new StringContent(
            System.Text.Json.JsonSerializer.Serialize(body),
            System.Text.Encoding.UTF8,
            "application/json");
}

/// <summary>
/// One result from the Python service: its status, its JSON
/// body if it had one, its text body if it did not, and
/// whether it succeeded.
/// </summary>
public sealed record UpstreamResponse(
    int StatusCode,
    string? Json,
    string? Text,
    bool IsSuccess)
{
    public static UpstreamResponse BadGateway(
        string detail) => new(
            (int)HttpStatusCode.BadGateway,
            System.Text.Json.JsonSerializer.Serialize(
                new { detail }),
            null,
            false);

    public static UpstreamResponse GatewayTimeout(
        string detail) => new(
            (int)HttpStatusCode.GatewayTimeout,
            System.Text.Json.JsonSerializer.Serialize(
                new { detail }),
            null,
            false);
}
