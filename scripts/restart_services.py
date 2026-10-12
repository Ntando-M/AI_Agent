"""
Restart the whole stack.

    venv/Scripts/python.exe scripts/restart_services.py

Kills whatever is holding the stack's ports, then hands off to
run_services.py. This exists because a crashed or Ctrl+C'd run
can leave an orphaned child still bound to :5000, :8000 or
:4200: the next start then fails with "address already in use"
while the health check still passes, because the *old* process
is the one answering it. That combination looks like a code bug
and is not one.

Ports are imported from run_services rather than repeated here,
so the two cannot drift apart. Both address families are
scanned: the Angular dev server listens on IPv6, which a plain
"netstat -p TCP" does not show.

Any extra arguments are passed straight through:

    ... restart_services.py --no-web
    ... restart_services.py --python-only
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from run_services import (  # noqa: E402
    GATEWAY_PORT,
    PYTHON_PORT,
    VENV_PYTHON,
    WEB_PORT,
)


RUN_SERVICES = SCRIPTS_DIR / "run_services.py"


def log(message: str) -> None:
    print(f"[restart] {message}", flush=True)


def listeners_on(port: int) -> list[int]:
    """
    Return the PIDs listening on a TCP port.

    Parsed from netstat rather than psutil: psutil is not a
    project dependency, and netstat ships with Windows. The
    port is matched against the local-address field only, so
    :8000 does not also match :18000.

    Both address families are scanned. "netstat -p TCP" is
    IPv4 only, and the Angular dev server listens on IPv6
    [::1] by default: scanning one family reported the port
    free while the frontend still held it.
    """

    output: list[str] = []

    for family in ("TCP", "TCPv6"):
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", family],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            log(f"could not run netstat -p {family}: {exc}")
            continue

        output.extend(result.stdout.splitlines())

    # Anchor on the field end: the address is a trimmed token
    # like "127.0.0.1:5000" or "[::1]:4200", with no trailing
    # whitespace to match. Anchoring also stops :8000 matching
    # :18000.
    pattern = re.compile(rf":{port}$")

    pids: set[int] = set()

    for line in output:
        if "LISTENING" not in line.upper():
            continue

        fields = line.split()

        # TCP  <local>  <foreign>  <state>  <pid>
        if len(fields) < 5:
            continue

        if not pattern.search(fields[1]):
            continue

        try:
            pids.add(int(fields[-1]))
        except ValueError:
            continue

    return sorted(pids)


def kill(pid: int, port: int) -> None:
    """
    Terminate a process holding a port.

    taskkill on Windows, a plain SIGTERM elsewhere. The
    escalation in run_services.terminate does not apply here:
    an orphaned service is already wedged, so it gets no
    grace period.

    The whole process tree is killed. npx spawns a child node
    for the Angular dev server, so killing only the listener's
    PID can leave the child holding the port.
    """

    if pid == os.getpid():
        return

    log(f"killing PID {pid} on port {port}")

    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        log(f"could not kill PID {pid}: {exc}")


def free_ports(ports: list[int]) -> None:
    """
    Clear every port the stack uses.

    Every port is checked before anything is started, not just
    the ones the current invocation will bind: a --python-only
    run should still be able to clear a stale gateway that is
    holding :5000, otherwise the next full run fails.
    """

    for port in ports:
        for pid in listeners_on(port):
            kill(pid, port)


def main() -> int:
    # Every argument belongs to run_services.py; this script has
    # no options of its own. Forwarding sys.argv verbatim keeps
    # flags and their values in order -- argparse's REMAINDER
    # cannot, because it hands back unrecognized flags and
    # positionals as separate lists and the pairing is lost.
    forwarded = sys.argv[1:]

    ports = [PYTHON_PORT, GATEWAY_PORT, WEB_PORT]

    log(f"freeing ports {', '.join(str(p) for p in ports)}")

    free_ports(ports)

    log("starting services")

    # Same reason run_services spawns the service with the venv
    # interpreter: launch the launcher with it too, so the whole
    # chain runs under one interpreter and the venv's site
    # packages are importable at every level.
    launcher = (
        str(VENV_PYTHON)
        if VENV_PYTHON.exists()
        else sys.executable
    )

    process = subprocess.Popen(
        [
            launcher,
            str(RUN_SERVICES),
            *forwarded,
        ]
    )

    try:
        return process.wait()
    except KeyboardInterrupt:
        # run_services receives the same Ctrl+C and tears the
        # stack down itself. Waiting for it to finish avoids
        # exiting while its children are still shutting down.
        return process.wait()


if __name__ == "__main__":
    sys.exit(main())
