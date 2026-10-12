using System.Net;
using ApiGateway;
using ApiGateway.Services;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace ApiGateway.Tests;

/// <summary>
/// A transport that answers from a script instead of a socket.
/// </summary>
public sealed class StubHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, HttpResponseMessage> _respond;

    public StubHandler(
        Func<HttpRequestMessage, HttpResponseMessage> respond)
    {
        _respond = respond;
    }

    /// <summary>
    /// Every request the client actually issued. Assertions
    /// read this rather than trusting the caller, so a test
    /// proves what went on the wire.
    /// </summary>
    public List<HttpRequestMessage> Requests { get; } = new();

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        Requests.Add(request);

        return Task.FromResult(_respond(request));
    }
}

/// <summary>
/// Builds a client wired to a stub transport, with no real
/// Python service required.
/// </summary>
internal static class TestClient
{
    public const string Secret = "test-secret-do-not-log";

    public static PythonAnalysisClient Build(
        StubHandler handler,
        string? apiKey = Secret,
        string headerName = "X-API-Key",
        int timeoutSeconds = 30,
        string baseUrl = "http://python.test")
    {
        var http = new HttpClient(handler)
        {
            BaseAddress = new Uri(baseUrl + "/"),
            Timeout = TimeSpan.FromSeconds(timeoutSeconds),
        };

        var options = Options.Create(
            new PythonServiceOptions
            {
                BaseUrl = baseUrl,
                ApiKey = apiKey ?? string.Empty,
                ApiKeyHeader = headerName,
                TimeoutSeconds = timeoutSeconds,
            });

        return new PythonAnalysisClient(
            http,
            options,
            NullLogger<PythonAnalysisClient>.Instance);
    }

    public static HttpResponseMessage Json(
        HttpStatusCode status,
        string body = "{}") => new(HttpStatusCode.OK)
    {
        StatusCode = status,
        Content = new StringContent(
            body,
            System.Text.Encoding.UTF8,
            "application/json"),
    };

    public static HttpResponseMessage Text(
        HttpStatusCode status,
        string body = "plain") => new(HttpStatusCode.OK)
    {
        StatusCode = status,
        Content = new StringContent(
            body,
            System.Text.Encoding.UTF8,
            "text/plain"),
    };
}
