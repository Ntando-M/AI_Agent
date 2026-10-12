using System.Net;
using ApiGateway.Services;

namespace ApiGateway.Tests;

/// <summary>
/// The gateway's job is to attach the shared secret and pass
/// everything else through untouched. These tests pin that
/// behaviour, because the secret is the one thing in this
/// repository that must never leak and the one thing that must
/// never go missing.
/// </summary>
public class PythonAnalysisClientTests
{
    // ====================================================
    // THE SECRET
    // ====================================================

    [Fact]
    public async Task AttachesTheSecretToEveryRequest()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(handler);

        await client.ForwardAsync(
            HttpMethod.Get, "/health", null);
        await client.ForwardAsync(
            HttpMethod.Get, "/sessions", null);

        Assert.Equal(2, handler.Requests.Count);

        foreach (var request in handler.Requests)
        {
            Assert.True(request.Headers.Contains(
                "X-API-Key"));
        }
    }

    [Fact]
    public async Task AttachesTheConfiguredSecretValue()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(handler);

        await client.ForwardAsync(
            HttpMethod.Get, "/health", null);

        var sent = handler.Requests[0]
            .Headers.GetValues("X-API-Key")
            .Single();

        Assert.Equal(TestClient.Secret, sent);
    }

    [Fact]
    public async Task HonoursACustomHeaderName()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(
            handler,
            headerName: "X-Custom-Key");

        await client.ForwardAsync(
            HttpMethod.Get, "/health", null);

        Assert.True(
            handler.Requests[0].Headers.Contains(
                "X-Custom-Key"));
    }

    [Fact]
    public void ReportsUnconfiguredWhenTheSecretIsMissing()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(
            handler,
            apiKey: string.Empty);

        Assert.False(client.IsConfigured);
    }

    [Fact]
    public void ReportsConfiguredWhenTheSecretIsPresent()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        Assert.True(TestClient.Build(handler).IsConfigured);
    }

    // ====================================================
    // PASS-THROUGH
    // ====================================================

    [Theory]
    [InlineData(HttpStatusCode.OK)]
    [InlineData(HttpStatusCode.BadRequest)]
    [InlineData(HttpStatusCode.NotFound)]
    [InlineData(HttpStatusCode.RequestTimeout)]
    public async Task PreservesTheUpstreamStatusCode(
        HttpStatusCode status)
    {
        // A 404 from the analysis service must stay a 404 with
        // its own message. Rewriting it to a generic gateway
        // error would hide what the engine actually said.
        var handler = new StubHandler(
            _ => TestClient.Json(
                status,
                """{"detail":"no such session"}"""));

        var client = TestClient.Build(handler);

        var result = await client.ForwardAsync(
            HttpMethod.Get, "/sessions/x", null);

        Assert.Equal((int)status, result.StatusCode);
        Assert.Contains(
            "no such session", result.Json!);
    }

    [Fact]
    public async Task SplitsJsonFromText()
    {
        var handler = new StubHandler(
            request => request.RequestUri!.AbsolutePath
                == "/health"
                    ? TestClient.Json(
                        HttpStatusCode.OK,
                        """{"status":"ok"}""")
                    : TestClient.Text(
                        HttpStatusCode.OK,
                        "not json"));

        var client = TestClient.Build(handler);

        var json = await client.ForwardAsync(
            HttpMethod.Get, "/health", null);

        Assert.NotNull(json.Json);
        Assert.Null(json.Text);

        var text = await client.ForwardAsync(
            HttpMethod.Get, "/other", null);

        Assert.NotNull(text.Text);
        Assert.Null(text.Json);
    }

    [Fact]
    public async Task ForwardsThePathVerbatim()
    {
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(handler);

        await client.ForwardAsync(
            HttpMethod.Get,
            "/sessions/abc-123",
            null);

        Assert.Equal(
            "/sessions/abc-123",
            handler.Requests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task ForwardsTheBodyContentType()
    {
        // Multipart boundaries must survive the hop or an
        // upload arrives corrupt. This is the reason uploads
        // are streamed as StreamContent rather than
        // re-serialised into a typed model.
        var handler = new StubHandler(
            _ => TestClient.Json(HttpStatusCode.OK));

        var client = TestClient.Build(handler);

        using var content = new StreamContent(
            new MemoryStream("Date,Revenue"u8.ToArray()));

        content.Headers.TryAddWithoutValidation(
            "Content-Type",
            "multipart/form-data; boundary=abc123");

        await client.ForwardAsync(
            HttpMethod.Post,
            "/datasets",
            content);

        Assert.Equal(
            "multipart/form-data; boundary=abc123",
            handler.Requests[0]
                .Content!.Headers.ContentType!.ToString());
    }

    [Fact]
    public async Task MarksSuccessOnlyFor2xx()
    {
        var handler = new StubHandler(
            request => request.RequestUri!.AbsolutePath
                == "/ok"
                    ? TestClient.Json(HttpStatusCode.OK)
                    : TestClient.Json(
                        HttpStatusCode.InternalServerError));

        var client = TestClient.Build(handler);

        Assert.True((await client.ForwardAsync(
            HttpMethod.Get, "/ok", null)).IsSuccess);

        Assert.False((await client.ForwardAsync(
            HttpMethod.Get, "/bad", null)).IsSuccess);
    }

    // ====================================================
    // FAILURE MODES
    // ====================================================

    [Fact]
    public async Task UnreachableServiceBecomes502()
    {
        var handler = new StubHandler(
            _ => throw new HttpRequestException(
                "connection refused"));

        var client = TestClient.Build(handler);

        var result = await client.ForwardAsync(
            HttpMethod.Get, "/health", null);

        Assert.Equal(502, result.StatusCode);
        Assert.Contains(
            "not reachable", result.Json!);
    }

    [Fact]
    public async Task TimeoutBecomes504Not502()
    {
        // A timeout and an unreachable service are different
        // problems for whoever is debugging. Collapsing them
        // into one code sends them looking in the wrong place.
        var handler = new StubHandler(
            _ => throw new TaskCanceledException());

        var client = TestClient.Build(handler);

        var result = await client.ForwardAsync(
            HttpMethod.Get, "/analyse", null);

        Assert.Equal(504, result.StatusCode);
        Assert.Contains(
            "did not respond in time", result.Json!);
    }

    [Fact]
    public async Task UpstreamErrorDetailIsNotSwallowed()
    {
        // The upload limits enforced on the Python side must
        // reach the browser through the gateway intact.
        var handler = new StubHandler(
            _ => TestClient.Json(
                HttpStatusCode.BadRequest,
                """
                {"detail":"Unsupported dataset type: '.exe' is not accepted."}
                """));

        var client = TestClient.Build(handler);

        var result = await client.ForwardAsync(
            HttpMethod.Post, "/datasets", null);

        Assert.Equal(400, result.StatusCode);
        Assert.Contains(
            "Unsupported dataset type", result.Json!);
    }
}
