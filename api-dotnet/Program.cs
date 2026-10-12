using ApiGateway;
using ApiGateway.Endpoints;
using ApiGateway.Services;

var builder = WebApplication.CreateBuilder(args);

// The gateway holds the shared secret in server-side
// configuration. It is never read from a request, never
// echoed in a response, and never logged.
builder.Services.Configure<PythonServiceOptions>(
    builder.Configuration.GetSection(
        PythonServiceOptions.SectionName));

builder.Services.AddHttpClient<PythonAnalysisClient>(
    (serviceProvider, client) =>
    {
        var options = serviceProvider
            .GetRequiredService<
                Microsoft.Extensions.Options.IOptions<
                    PythonServiceOptions>>()
            .Value;

        client.BaseAddress = new Uri(
            options.BaseUrl.TrimEnd('/') + "/");
    });

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddCors(options =>
{
    // Angular's dev server and nothing else. A wildcard
    // origin on a service that can delete sessions and read
    // datasets would let any site in the user's browser
    // drive the engine.
    options.AddPolicy("AngularDev", policy =>
    {
        policy
            .WithOrigins(
                builder.Configuration
                    .GetSection("Cors:AllowedOrigins")
                    .Get<string[]>()
                ?? new[]
                {
                    "http://localhost:4200",
                })
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

// Startup fails fast when the key is missing. A gateway
// that starts without it silently forwards unauthenticated
// requests to a service that rejects them, which looks like
// a Python outage rather than a configuration error.
var pythonOptions = app.Configuration
    .GetSection(PythonServiceOptions.SectionName)
    .Get<PythonServiceOptions>()
    ?? new PythonServiceOptions();

if (string.IsNullOrWhiteSpace(pythonOptions.ApiKey))
{
    throw new InvalidOperationException(
        "PythonService:ApiKey is not configured. The "
        + "gateway refuses to start without the shared "
        + "key. Set PythonService__ApiKey in user secrets "
        + "or the environment.");
}

app.UseCors("AngularDev");

app.MapAnalysisProxy();

app.Run();
