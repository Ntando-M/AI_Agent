namespace ApiGateway;

/// <summary>
/// Where the Python analysis service lives, and the shared
/// secret that proves this gateway may talk to it.
///
/// The key lives here and never leaves. That is the whole
/// reason this layer exists: a browser talking straight to
/// FastAPI would have to carry the key, and every user would
/// receive it.
/// </summary>
public sealed class PythonServiceOptions
{
    public const string SectionName = "PythonService";

    /// <summary>
    /// Base address of the FastAPI service.
    /// </summary>
    public string BaseUrl { get; set; } = "http://127.0.0.1:8000";

    /// <summary>
    /// Shared secret sent as X-API-Key on every upstream call.
    /// </summary>
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Header name the Python service expects.
    /// </summary>
    public string ApiKeyHeader { get; set; } = "X-API-Key";

    /// <summary>
    /// Per-request timeout.
    ///
    /// Generous, because an analysis turn legitimately runs a
    /// planner call, deterministic tools, and a synthesis call.
    /// The Python side is the authority on its own budget; the
    /// gateway must not cut a legitimate analysis short.
    /// </summary>
    public int TimeoutSeconds { get; set; } = 300;
}
