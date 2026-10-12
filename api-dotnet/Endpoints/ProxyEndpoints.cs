using ApiGateway.Services;

namespace ApiGateway.Endpoints;

/// <summary>
/// Proxies the Python analysis service.
///
/// The gateway deliberately owns no analysis logic. Every
/// route here forwards to the same FastAPI endpoints the
/// Python tests exercise, adds the server-held API key, and
/// returns what came back. That is the entire job: the
/// reasoning engine stays in Python, and the CLI, the API
/// and the browser all reach the same one.
/// </summary>
public static class ProxyEndpoints
{
    public static void MapAnalysisProxy(
        this WebApplication app)
    {
        var group = app.MapGroup("/api");

        // -------------------------------------------------------
        // HEALTH
        // -------------------------------------------------------

        group.MapGet("/health", async (
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
        {
            var upstream = await python.ForwardAsync(
                HttpMethod.Get,
                "/health",
                null,
                cancellationToken);

            return Results.Content(
                upstream.Json ?? upstream.Text,
                "application/json",
                statusCode: upstream.StatusCode);
        })
        .WithName("Health")
        .WithTags("health");

        // -------------------------------------------------------
        // SESSIONS
        // -------------------------------------------------------

        group.MapGet("/sessions", async (
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                "/sessions",
                null,
                null,
                cancellationToken))
        .WithName("ListSessions")
        .WithTags("sessions");

        group.MapPost("/sessions", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/sessions",
                null,
                await ReadJsonAsync(
                    request,
                    cancellationToken),
                cancellationToken))
        .WithName("CreateSession")
        .WithTags("sessions");

        group.MapGet("/sessions/{sessionId}", async (
            string sessionId,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                $"/sessions/{Uri.EscapeDataString(sessionId)}",
                null,
                null,
                cancellationToken))
        .WithName("GetSession")
        .WithTags("sessions");

        group.MapDelete("/sessions/{sessionId}", async (
            string sessionId,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Delete,
                $"/sessions/{Uri.EscapeDataString(sessionId)}",
                null,
                null,
                cancellationToken))
        .WithName("DeleteSession")
        .WithTags("sessions");

        // -------------------------------------------------------
        // CHAT AND ANALYSIS
        // -------------------------------------------------------

        group.MapPost("/chat", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/chat",
                null,
                await ReadJsonAsync(
                    request,
                    cancellationToken),
                cancellationToken))
        .WithName("Chat")
        .WithTags("analysis");

        group.MapPost("/analyse", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/analyse",
                null,
                await ReadJsonAsync(
                    request,
                    cancellationToken),
                cancellationToken))
        .WithName("Analyse")
        .WithTags("analysis");

        // -------------------------------------------------------
        // DATASETS
        // -------------------------------------------------------

        group.MapGet("/datasets", async (
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                "/datasets",
                null,
                null,
                cancellationToken))
        .WithName("ListDatasets")
        .WithTags("datasets");

        group.MapPost("/datasets", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/datasets",
                await ForwardContentAsync(
                    request,
                    cancellationToken),
                null,
                cancellationToken))
        .WithName("UploadDataset")
        .WithTags("datasets")
        .DisableAntiforgery();

        group.MapDelete("/datasets/{name}", async (
            string name,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Delete,
                $"/datasets/{Uri.EscapeDataString(name)}",
                null,
                null,
                cancellationToken))
        .WithName("DeleteDataset")
        .WithTags("datasets");

        // -------------------------------------------------------
        // DOCUMENTS
        // -------------------------------------------------------

        group.MapGet("/documents", async (
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                "/documents",
                null,
                null,
                cancellationToken))
        .WithName("ListDocuments")
        .WithTags("documents");

        group.MapPost("/documents", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/documents",
                await ForwardContentAsync(
                    request,
                    cancellationToken),
                null,
                cancellationToken))
        .WithName("UploadDocument")
        .WithTags("documents")
        .DisableAntiforgery();

        group.MapDelete("/documents/{name}", async (
            string name,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Delete,
                $"/documents/{Uri.EscapeDataString(name)}",
                null,
                null,
                cancellationToken))
        .WithName("DeleteDocument")
        .WithTags("documents");

        // -------------------------------------------------------
        // REPORTS
        // -------------------------------------------------------

        group.MapGet("/reports", async (
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                "/reports",
                null,
                null,
                cancellationToken))
        .WithName("ListReports")
        .WithTags("reports");

        group.MapPost("/reports", async (
            HttpRequest request,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Post,
                "/reports",
                null,
                await ReadJsonAsync(
                    request,
                    cancellationToken),
                cancellationToken))
        .WithName("GenerateReport")
        .WithTags("reports");

        group.MapGet("/reports/{reportId}", async (
            string reportId,
            PythonAnalysisClient python,
            CancellationToken cancellationToken) =>
            await ProxyAsync(
                python,
                HttpMethod.Get,
                $"/reports/{Uri.EscapeDataString(reportId)}",
                null,
                null,
                cancellationToken))
        .WithName("GetReport")
        .WithTags("reports");
    }

    // ========================================================
    // HELPERS
    // ========================================================

    private static async Task<HttpContent?> ReadJsonAsync(
        HttpRequest request,
        CancellationToken cancellationToken)
    {
        if (request.ContentLength is null or 0)
        {
            return null;
        }

        var body = await new StreamReader(
            request.Body)
            .ReadToEndAsync(cancellationToken);

        if (string.IsNullOrWhiteSpace(body))
        {
            return null;
        }

        return new StringContent(
            body,
            System.Text.Encoding.UTF8,
            request.ContentType
                ?? "application/json");
    }

    /// <summary>
    /// Stream an upload through unchanged.
    ///
    /// The content type and the stream itself are preserved
    /// so multipart boundaries and file bytes survive the
    /// hop. Re-buffering an upload here would mean this
    /// process holds a whole dataset in memory for no reason.
    /// </summary>
    private static Task<HttpContent?> ForwardContentAsync(
        HttpRequest request,
        CancellationToken cancellationToken)
    {
        if (request.ContentLength is null or 0)
        {
            return Task.FromResult<HttpContent?>(
                null);
        }

        var content = new StreamContent(
            request.Body);

        if (request.ContentType is not null)
        {
            content.Headers.TryAddWithoutValidation(
                "Content-Type",
                request.ContentType);
        }

        return Task.FromResult<HttpContent?>(
            content);
    }

    private static async Task<IResult> ProxyAsync(
        PythonAnalysisClient python,
        HttpMethod method,
        string path,
        HttpContent? forwardedContent,
        HttpContent? body,
        CancellationToken cancellationToken)
    {
        var upstream = await python.ForwardAsync(
            method,
            path,
            body ?? forwardedContent,
            cancellationToken);

        if (upstream.Json is not null)
        {
            return Results.Content(
                upstream.Json,
                "application/json",
                statusCode: upstream.StatusCode);
        }

        if (upstream.Text is not null)
        {
            return Results.Content(
                upstream.Text,
                "text/plain",
                statusCode: upstream.StatusCode);
        }

        return Results.StatusCode(
            upstream.StatusCode);
    }
}
