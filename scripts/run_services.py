"""
Start the whole stack with one command.

    venv/Scripts/python.exe scripts/run_services.py

Runs the analysis service, the gateway and the Angular client,
waits until each is actually healthy before starting the next,
prints the URLs, and shuts them all down together on Ctrl+C.

Why a script rather than three terminals: the analysis service
must be reachable before the gateway is useful, and the
gateway's whole job is to hold a key it resolved from user
secrets. Starting them by hand in the wrong order produces a
gateway that answers 502 for reasons that look like a code
bug. This makes the ordering explicit and checks it.

The Python API is started as a child process rather than
imported, so Ctrl+C stops the uvicorn server cleanly instead
of leaving a half-torn-down event loop behind in this
process.

Use --no-web to leave the Angular client out; the two
services alone are enough when only the API is being worked
on.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# The project's dependencies live in this venv, so the services
# must run under this interpreter rather than whichever python
# happened to launch the launcher script.
VENV_PYTHON = (
    REPO_ROOT / "venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else REPO_ROOT / "venv" / "bin" / "python"
)

PYTHON_HOST = "127.0.0.1"
PYTHON_PORT = 8000
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 5000

# The dev server is bound to this address explicitly, so the
# health check polls the same one. "localhost" would resolve to
# ::1 first and hide a server that is only listening on IPv4.
WEB_HOST = "127.0.0.1"
WEB_PORT = 4200

STARTUP_TIMEOUT_SECONDS = 90


BANNER = r"""
  +------------------------------------------------------+
  |        AI Data Analyst - full stack                  |
  +------------------------------------------------------+
"""


def log(message: str) -> None:
    print(f"[run] {message}", flush=True)


def stream_output(
    stream,
    prefix: str,
    stop_event: threading.Event,
) -> None:
    """
    Relay a child process's output with a prefix.

    Read line by line and stop on the stop event so the
    reader thread cannot keep the interpreter alive at exit.
    A trailing partial line is ignored; losing the last line
    of a shutdown message is preferable to hanging.
    """

    try:
        for line in iter(stream.readline, ""):
            if stop_event.is_set():
                break

            if line.strip():
                print(
                    f"{prefix} {line.rstrip()}",
                    flush=True,
                )
    except (ValueError, OSError):
        # The pipe closes underneath us during shutdown.
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def wait_for_health(
    url: str,
    label: str,
    stop_event: threading.Event,
    timeout: int = STARTUP_TIMEOUT_SECONDS,
) -> bool:
    """
    Poll a health endpoint until it answers or time runs out.

    Polling rather than sleeping a fixed interval: a fixed
    sleep is either slow on a fast machine or flaky on a slow
    one, and the first run builds the .NET project, which can
    take considerably longer than any later run.
    """

    deadline = time.monotonic() + timeout
    attempt = 0

    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False

        attempt += 1

        try:
            with urllib.request.urlopen(
                url,
                timeout=2,
            ) as response:
                if response.status == 200:
                    log(
                        f"{label} is healthy "
                        f"after {attempt} attempt(s)"
                    )
                    return True
        except (urllib.error.URLError, OSError):
            pass

        time.sleep(1)

    log(f"{label} did NOT become healthy within {timeout}s")
    return False


def child_environment(
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Environment for the child processes.

    Inherits this process's environment, which is what makes
    the venv's activated PATH and any exported variables
    visible to both services.

    ASPNETCORE_ENVIRONMENT is pinned rather than left to
    default. Swagger UI is only mounted when the environment
    is Development, so relying on the implicit default meant
    the gateway's own documented URL worked or did not
    depending on how it was launched.
    """

    environment = dict(os.environ)

    environment.setdefault(
        "ASPNETCORE_ENVIRONMENT", "Development"
    )

    if extra:
        environment.update(extra)

    return environment


def resolve_command(name: str) -> str:
    """
    Find a command, including Windows shims.

    On Windows, npm's entry points are .cmd shims rather than
    real executables. Popen does not consult PATHEXT, so
    spawning "npx" directly raises WinError 2 even though the
    command works from a shell. Resolving the shim explicitly
    avoids needing shell=True, which would change how arguments
    are quoted.
    """

    resolved = shutil.which(name)

    if resolved:
        return resolved

    if os.name == "nt":
        for extension in (".cmd", ".exe", ".bat"):
            candidate = shutil.which(
                f"{name}{extension}"
            )

            if candidate:
                return candidate

    return name


def spawn(
    command: list[str],
    label: str,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> tuple[
    subprocess.Popen,
    list[threading.Thread],
    threading.Event,
]:
    """
    Start a child process and relay its output.
    """

    stop_event = threading.Event()

    # Resolve only the program, never the arguments: passing
    # the whole list through which() would mangle paths.
    resolved = [resolve_command(command[0]), *command[1:]]

    process = subprocess.Popen(
        resolved,
        cwd=str(cwd),
        env=child_environment(extra_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    readers = [
        threading.Thread(
            target=stream_output,
            args=(
                process.stdout,
                f"{label:8}",
                stop_event,
            ),
            daemon=True,
        )
    ]

    for reader in readers:
        reader.start()

    return process, readers, stop_event


def terminate(
    process: subprocess.Popen,
    label: str,
    timeout: int = 10,
) -> None:
    """
    Stop a child process, escalating if it ignores the polite
    signal.

    uvicorn handles SIGTERM and shuts down cleanly; dotnet
    also handles it. The kill escalation exists because a
    wedged child would otherwise leave the port bound after
    the launcher exits, and the next run would fail with a
    confusing "address already in use".
    """

    if process.poll() is not None:
        return

    log(f"stopping {label}")

    try:
        process.terminate()

        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"{label} ignored terminate, killing")
        process.kill()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            log(f"{label} could not be killed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start the FastAPI analysis service, the ASP.NET "
            "Core gateway and the Angular client together."
        )
    )

    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Start only the FastAPI analysis service.",
    )

    parser.add_argument(
        "--gateway-only",
        action="store_true",
        help="Start only the ASP.NET Core gateway.",
    )

    parser.add_argument(
        "--no-web",
        action="store_true",
        help=(
            "Skip the Angular client on :4200. The client is "
            "started by default; this disables it."
        ),
    )

    parser.add_argument(
        "--web-port",
        type=int,
        default=WEB_PORT,
    )

    parser.add_argument(
        "--gateway-port",
        type=int,
        default=GATEWAY_PORT,
    )

    parser.add_argument(
        "--python-port",
        type=int,
        default=PYTHON_PORT,
    )

    args = parser.parse_args()

    if args.python_only and args.gateway_only:
        parser.error(
            "--python-only and --gateway-only are mutually "
            "exclusive"
        )

    start_python = not args.gateway_only
    start_gateway = not args.python_only

    # The client is part of the default stack, but it is useless
    # on its own: its /api proxy targets the gateway, so with
    # --python-only it would spend the startup timeout failing
    # to reach :5000 and then tear the whole stack down. Only
    # start it when the gateway is there for it to talk to.
    start_web = not args.no_web and start_gateway

    gateway_project = REPO_ROOT / "api-dotnet"
    web_project = REPO_ROOT / "web"

    if start_gateway and not gateway_project.exists():
        log(
            f"gateway project not found at {gateway_project}. "
            f"Run without --gateway-only, or restore the "
            f"directory."
        )
        return 1

    if start_web:
        # The client needs node_modules before ng serve will
        # start. Checking here gives a clear message rather
        # than a wall of resolver errors from npm.
        if not (web_project / "node_modules").exists():
            log(
                f"web dependencies not installed. Run: "
                f"cd web && npm install (use the official "
                f"Node install, not the bundled one)"
            )
            return 1

    processes: list[tuple[str, subprocess.Popen]] = []
    reader_threads: list[threading.Thread] = []
    stop_events: list[threading.Event] = []

    # Ctrl+C should tear the stack down, not leave orphans.
    def handle_interrupt(*_args) -> None:
        raise KeyboardInterrupt

    signal.signal(
        signal.SIGINT, handle_interrupt
    )

    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM, handle_interrupt
        )

    print(BANNER)

    if start_python and not VENV_PYTHON.exists():
        log(
            f"venv interpreter not found at {VENV_PYTHON}. "
            f"Create the venv and install requirements, or run "
            f"the launcher with the venv's own python."
        )
        return 1

    try:
        if start_python:
            log(
                "starting analysis service on "
                f"http://{PYTHON_HOST}:{args.python_port}"
            )

            python_process, readers, stop_event = spawn(
                [
                    str(VENV_PYTHON),
                    "-m",
                    "uvicorn",
                    "api.app:get_app",
                    "--factory",
                    "--host",
                    PYTHON_HOST,
                    "--port",
                    str(args.python_port),
                ],
                "python",
                REPO_ROOT,
            )

            processes.append(
                ("analysis service", python_process)
            )
            reader_threads.extend(readers)
            stop_events.append(stop_event)

            # The gateway proxies to this, so it has to be up
            # before the gateway is declared ready.
            if not wait_for_health(
                f"http://{PYTHON_HOST}:{args.python_port}"
                "/health",
                "analysis service",
                stop_events[-1],
            ):
                terminate(python_process, "analysis service")
                return 1

        if start_gateway:
            log(
                "starting gateway on "
                f"http://{GATEWAY_HOST}:{args.gateway_port}"
            )

            gateway_process, readers, stop_event = spawn(
                [
                    "dotnet",
                    "run",
                    "--project",
                    str(gateway_project),
                    "--urls",
                    f"http://{GATEWAY_HOST}:{args.gateway_port}",
                ],
                "gateway",
                REPO_ROOT,
            )

            processes.append(
                ("gateway", gateway_process)
            )
            reader_threads.extend(readers)
            stop_events.append(stop_event)

            # The gateway's /api/health proxies to the Python
            # service, so a 200 here proves the whole chain.
            if start_python:
                if not wait_for_health(
                    f"http://{GATEWAY_HOST}:{args.gateway_port}"
                    "/api/health",
                    "gateway",
                    stop_events[-1],
                ):
                    for label, process in processes:
                        terminate(process, label)
                    return 1
            else:
                log(
                    "skipping gateway health check: "
                    "the analysis service was not started "
                    "by this script"
                )

        if start_web:
            log(
                "starting web client on "
                f"http://{WEB_HOST}:{args.web_port}"
            )

            web_process, readers, stop_event = spawn(
                [
                    "npx",
                    "ng",
                    "serve",
                    # Bind IPv4 explicitly. Left to its default,
                    # ng serve listens on IPv6 [::1] only, which
                    # means 127.0.0.1 refuses and any tool that
                    # does not try ::1 first sees a dead server.
                    "--host",
                    WEB_HOST,
                    "--port",
                    str(args.web_port),
                ],
                "web",
                web_project,
            )

            processes.append(("web client", web_process))
            reader_threads.extend(readers)
            stop_events.append(stop_event)

            # The dev server proxies /api to the gateway, so a
            # 200 on that path proves the browser's own route
            # to the analysis engine is wired end to end.
            if not wait_for_health(
                f"http://{WEB_HOST}:{args.web_port}"
                "/api/health",
                "web client",
                stop_events[-1],
            ):
                for label, process in processes:
                    terminate(process, label)
                return 1

        print()
        print("  Stack is up.")
        print()

        if start_web:
            print(
                f"    Web client http://{WEB_HOST}:"
                f"{args.web_port}"
            )

        if start_gateway:
            print(
                "    Swagger    "
                f"http://{GATEWAY_HOST}:{args.gateway_port}"
                "/swagger"
            )
            print(
                "    Proxied    "
                f"http://{GATEWAY_HOST}:{args.gateway_port}"
                "/api/health"
            )

        if start_python:
            print(
                "    FastAPI    "
                f"http://{PYTHON_HOST}:{args.python_port}"
                "/docs"
            )

        print()
        print(
            "  The gateway attaches the API key for you. "
            "You do not send"
        )
        print(
            "  X-API-Key when calling it. Calling FastAPI "
            "directly does"
        )
        print("  require the key.")
        print()
        print("  Ctrl+C stops everything.")
        print()

        # Park until a child exits or the user interrupts.
        # Polling rather than waiting on one process means a
        # crash in any service is noticed.
        while True:
            for label, process in processes:
                if process.poll() is not None:
                    log(
                        f"{label} exited with code "
                        f"{process.returncode}"
                    )
                    raise KeyboardInterrupt

            time.sleep(1)

    except KeyboardInterrupt:
        print()

        for event in stop_events:
            event.set()

        for label, process in reversed(processes):
            terminate(process, label)

        log("stack stopped")

        return 0

    except Exception as exc:
        # A failure partway through startup must not leave the
        # services that did start running. Without this, a
        # crash while spawning the third process orphaned the
        # first two, holding their ports so the next run failed
        # with "address already in use".
        print()

        for event in stop_events:
            event.set()

        for label, process in reversed(processes):
            terminate(process, label)

        log(
            f"launcher failed: {type(exc).__name__}: {exc}"
        )

        return 1

    finally:
        for event in stop_events:
            event.set()


if __name__ == "__main__":
    sys.exit(main())
