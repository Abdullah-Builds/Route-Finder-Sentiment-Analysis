# import http.server
# import socketserver
# import webbrowser
# import os
# import threading
# import time
# import sys
# from dotenv import load_dotenv
# load_dotenv()

# PORT = int(os.getenv("PORT", 8000))
# FILE = "astar_visualizer.html"

# def start_server():
#     Handler = http.server.SimpleHTTPRequestHandler
#     # Allow address reuse to avoid "Address already in use" errors on restart
#     socketserver.TCPServer.allow_reuse_address = True
#     try:
#         with socketserver.TCPServer(("", PORT), Handler) as httpd:
#             print(f"\n🚀 Server started at http://localhost:{PORT}")
#             httpd.serve_forever()
#     except Exception as e:
#         print(f"❌ Failed to start server: {e}")
#         sys.exit(1)

# if __name__ == "__main__":
#     if not os.path.exists(FILE):
#         print(f"❌ Error: {FILE} not found in the current directory.")
#         sys.exit(1)

#     # Start server in a background thread
#     server_thread = threading.Thread(target=start_server, daemon=True)
#     server_thread.start()

#     # Wait a moment for the server to initialize
#     time.sleep(1)

#     # Open the visualizer in the browser
#     url = f"http://localhost:{PORT}/{FILE}"
#     print(f"🌐 Opening {FILE} in your browser...")
#     try:
#         webbrowser.open(url)
#     except Exception as e:
#         print(f"⚠️ Could not open browser automatically: {e}")
#         print(f"Please open this URL manually: {url}")

#     print("\n💡 Tip: Press Ctrl+C to stop the server when you are done.")
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\n🛑 Stopping server...")
#         sys.exit(0)


from __future__ import annotations

import argparse
import http.server
import json
import logging
import os
import signal
import socket
import socketserver
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional


# ── Package-level constants ──────────────────────────────────────────────────
VERSION = "2.0.0"
DEFAULT_PORT = int(os.getenv("PORT",       8000))
DEFAULT_TRACE = os.getenv("TRACE_FILE",     "astar_trace.json")
DEFAULT_HTML = os.getenv("HTML_FILE",      "astar_visualizer.html")
DEFAULT_RANGE = 10     # consecutive ports to try on collision
PROBE_TIMEOUT = 6.0    # seconds to wait for socket readiness
WATCH_INTERVAL = 1.5    # seconds between file-change polls

# Global events — set to co-ordinate threads without shared mutable state
_SERVER_READY = threading.Event()
_SHUTDOWN = threading.Event()

# Module-level logger; configured in main() after args are parsed
log: logging.Logger = logging.getLogger("astar-viewer")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="view_animation",
        description="Serve the A* Search Visualizer and open it in a browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--port", "-p", type=int, default=DEFAULT_PORT, metavar="PORT",
        help=f"Preferred port (default: {DEFAULT_PORT}). "
        "Tries the next N ports automatically if busy.",
    )
    p.add_argument(
        "--host", default="localhost", metavar="HOST",
        help="Interface to bind. "
             "Use 0.0.0.0 to expose on your local network (default: localhost).",
    )
    p.add_argument(
        "--trace", default=DEFAULT_TRACE, metavar="FILE",
        help=f"Path to the A* trace JSON file (default: {DEFAULT_TRACE}).",
    )
    p.add_argument(
        "--html", default=DEFAULT_HTML, metavar="FILE",
        help=f"Path to the visualizer HTML file (default: {DEFAULT_HTML}).",
    )
    p.add_argument(
        "--port-range", type=int, default=DEFAULT_RANGE, metavar="N",
        help=f"Max consecutive ports to try if preferred port is busy "
        f"(default: {DEFAULT_RANGE}).",
    )
    p.add_argument(
        "--no-browser", action="store_true",
        help="Start the server without opening a browser tab.",
    )
    p.add_argument(
        "--watch", "-w", action="store_true",
        help="Watch the trace file for changes and print a reload reminder.",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Log every HTTP request (useful for debugging).",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}",
    )
    return p


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


# Keys that must exist in trace["meta"]
_REQUIRED_META = (
    "start_id", "goal_id",
    "start_lat", "start_lon",
    "goal_lat", "goal_lon",
    "total_dist_m", "total_time_s",
    "nodes_explored", "total_frames",
)


def _validate_trace(path: Path) -> None:
    """
    Load and lightly validate the trace JSON.
    Raises SystemExit with a clear message on any problem.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        log.error("Cannot read trace file: %s", exc)
        sys.exit(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Trace file is not valid JSON: %s", exc)
        sys.exit(1)

    if not isinstance(data, dict):
        log.error("Trace file must be a JSON object at the top level.")
        sys.exit(1)

    for key in ("meta", "frames", "graph_nodes"):
        if key not in data:
            log.error("Trace file is missing required top-level key: '%s'", key)
            sys.exit(1)

    missing_meta = [k for k in _REQUIRED_META if k not in data["meta"]]
    if missing_meta:
        log.error("Trace 'meta' block is missing keys: %s", missing_meta)
        sys.exit(1)

    if not isinstance(data["frames"], list):
        log.error("Trace 'frames' must be a JSON list.")
        sys.exit(1)

    if not isinstance(data["graph_nodes"], dict):
        log.error("Trace 'graph_nodes' must be a JSON object.")
        sys.exit(1)

    n_frames = len(data["frames"])
    n_nodes = len(data["graph_nodes"])
    log.info(
        "Trace validated — %s frames, %s graph nodes.",
        f"{n_frames:,}", f"{n_nodes:,}",
    )


def _validate_files(html: str, trace: str) -> None:
    """Check both required files exist and the trace passes schema validation."""
    errors: list[str] = []

    html_path = Path(html)
    trace_path = Path(trace)

    if not html_path.exists():
        errors.append(f"HTML file not found  : {html_path.resolve()}")
    elif not html_path.is_file():
        errors.append(
            f"HTML path is not a regular file: {html_path.resolve()}")

    if not trace_path.exists():
        errors.append(f"Trace file not found : {trace_path.resolve()}")
    elif not trace_path.is_file():
        errors.append(
            f"Trace path is not a regular file: {trace_path.resolve()}")

    if errors:
        for e in errors:
            log.error("  ✗  %s", e)
        log.error("Fix the above and re-run.")
        sys.exit(1)

    _validate_trace(trace_path)


def _is_port_free(host: str, port: int) -> bool:
    """Return True if *port* is available on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_free_port(host: str, start: int, port_range: int) -> int:
    """
    Return the first free port in ``[start, start + port_range)``.
    Exits with a diagnostic message if none are available.
    """
    for port in range(start, start + port_range):
        if _is_port_free(host, port):
            if port != start:
                log.warning(
                    "Port %d is in use — falling back to port %d.", start, port
                )
            return port

    log.error(
        "No free port found in range %d–%d on '%s'. "
        "Try --port <other> or increase --port-range.",
        start, start + port_range - 1, host,
    )
    sys.exit(1)


def _wait_for_server(host: str, port: int, timeout: float) -> bool:
    """
    Actively probe the TCP port until it accepts a connection or *timeout* elapses.
    More reliable than a fixed ``time.sleep()``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _make_handler(verbose: bool) -> type:
    """Return an HTTP handler class with appropriate logging and security headers."""

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            if verbose:
                log.debug("HTTP  " + (fmt % args))

        def log_error(self, fmt: str, *args) -> None:
            log.warning("HTTP error — " + (fmt % args))

        def end_headers(self) -> None:
            self.send_header(
                "Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("X-Content-Type-Options", "nosniff")
            super().end_headers()

    return _Handler


class _ReadyTCPServer(socketserver.TCPServer):
    """
    TCPServer subclass that signals a threading.Event once the socket is bound,
    so the main thread knows the server is truly ready before opening the browser.
    """

    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type,
        ready_event: threading.Event,
    ) -> None:
        self._ready_event = ready_event
        super().__init__(server_address, RequestHandlerClass)

    def server_bind(self) -> None:
        super().server_bind()
        self._ready_event.set()


def _run_server(host: str, port: int, handler: type) -> None:
    """
    Target function for the server daemon thread.
    Creates the TCP server, signals readiness, then serves until _SHUTDOWN is set.
    """
    try:
        with _ReadyTCPServer((host, port), handler, _SERVER_READY) as httpd:
            # serve_forever() blocks; we wake it up via a polling interval
            # so it exits cleanly once _SHUTDOWN is set externally.
            while not _SHUTDOWN.is_set():
                httpd.handle_request()
    except OSError as exc:
        log.critical("Server thread crashed: %s", exc)
        _SHUTDOWN.set()


def _watch_trace(trace_file: str, url: str) -> None:
    """
    Poll the trace file's mtime every WATCH_INTERVAL seconds.
    Prints a reload reminder whenever the file is replaced/updated.
    Runs in a daemon thread; exits when _SHUTDOWN is set.
    """
    path = Path(trace_file)
    last_mtime: Optional[float] = path.stat(
    ).st_mtime if path.exists() else None

    while not _SHUTDOWN.is_set():
        _SHUTDOWN.wait(timeout=WATCH_INTERVAL)
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue

        if last_mtime is not None and mtime != last_mtime:
            log.info(
                "Trace file updated — refresh your browser to see the new run.\n"
                "          URL : %s",
                url,
            )
        last_mtime = mtime


def _install_signal_handlers() -> None:
    """Map SIGINT and SIGTERM to a clean shutdown via the _SHUTDOWN event."""

    def _handler(signum: int, _frame) -> None:
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = str(signum)
        log.info("Received %s — shutting down…", name)
        _SHUTDOWN.set()

    signal.signal(signal.SIGINT,  _handler)
    signal.signal(signal.SIGTERM, _handler)


def _print_banner(html: str, trace: str, url: str) -> None:
    W = 60
    bar = "─" * W
    rows = [
        ("Visualizer", html),
        ("Trace",      trace),
        ("URL",        url),
        ("Stop",       "Ctrl+C  (or SIGTERM)"),
    ]
    print(f"\n  {bar}")
    print(f"  {'A* Search Visualizer  v' + VERSION:^{W}}")
    print(f"  {bar}")
    for label, value in rows:
        print(f"  {label:<14}: {value}")
    print(f"  {bar}\n")


def main() -> None:
    args = _build_parser().parse_args()

    _setup_logging(args.verbose)

    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)

    log.info("Working directory: %s", script_dir)

    # 1. Validate files before touching the network
    _validate_files(args.html, args.trace)

    # 2. Find a usable port
    port = _find_free_port(args.host, args.port, args.port_range)
    url = f"http://{args.host}:{port}/{args.html}"

    _print_banner(args.html, args.trace, url)

    # 3. Install OS signal handlers
    _install_signal_handlers()

    # 4. Start HTTP server in a daemon thread
    handler = _make_handler(args.verbose)
    server_thread = threading.Thread(
        target=_run_server,
        args=(args.host, port, handler),
        name="http-server",
        daemon=True,
    )
    server_thread.start()

    # 5. Wait until the socket is genuinely accepting connections
    log.debug("Probing server readiness…")
    if not _wait_for_server(args.host, port, PROBE_TIMEOUT):
        log.error(
            "Server did not become ready within %.1fs. "
            "Check for firewall rules or antivirus blocking the port.",
            PROBE_TIMEOUT,
        )
        _SHUTDOWN.set()
        sys.exit(1)

    log.info("Server is ready.")

    # 6. Open browser (unless suppressed)
    if args.no_browser:
        log.info("--no-browser: open manually → %s", url)
    else:
        log.info("Opening browser → %s", url)
        try:
            webbrowser.open(url)
        except Exception as exc:
            log.warning("Could not open browser automatically (%s).", exc)
            log.info("Open manually → %s", url)

    # 7. Optional trace watcher
    if args.watch:
        watch_thread = threading.Thread(
            target=_watch_trace,
            args=(args.trace, url),
            name="file-watcher",
            daemon=True,
        )
        watch_thread.start()
        log.info("Watching '%s' for changes…", args.trace)

    # 8. Block the main thread until a shutdown signal arrives
    try:
        while not _SHUTDOWN.is_set():
            _SHUTDOWN.wait(timeout=1.0)
    except KeyboardInterrupt:
        # Defensive fallback if the signal handler races on Windows
        _SHUTDOWN.set()

    log.info("Server stopped. Goodbye.")
    sys.exit(0)


if __name__ == "__main__":
    main()
