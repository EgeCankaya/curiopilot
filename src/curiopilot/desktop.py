"""PyWebView desktop launcher for CurioPilot."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)

DESKTOP_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)


class _ReaderBridge:
    """Manages a single reusable pywebview Reader window."""

    def __init__(self) -> None:
        self._reader_window = None
        self._lock = threading.Lock()

    def open_reader(self, url: str, title: str | None = None) -> bool:
        import webview

        with self._lock:
            win = self._reader_window
            if win is not None:
                try:
                    win.load_url(url)
                    if title:
                        win.set_title(title)
                    win.show()
                    win.restore()
                    return True
                except Exception:
                    self._reader_window = None

            new_win = webview.create_window(
                title or "Reader",
                url,
                width=1100,
                height=850,
                min_size=(600, 400),
            )
            self._reader_window = new_win

            def _on_closed():
                with self._lock:
                    if self._reader_window is new_win:
                        self._reader_window = None

            new_win.events.closed += _on_closed
            return True


def launch_app(
    config_path: str | Path = "config.yaml",
    port: int = 19231,
    debug: bool = False,
) -> None:
    """Launch CurioPilot as a native desktop window.

    1. Starts the FastAPI/uvicorn server in a daemon thread.
    2. Waits until the server is ready.
    3. Opens a pywebview window pointing to the local server.
    4. Blocks until the window is closed, then signals uvicorn to shut down.
    """
    import uvicorn
    import webview

    from curiopilot.api.app import create_app

    bridge = _ReaderBridge()
    app = create_app(config_path=str(config_path), ui_bridge=bridge)
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    uv_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info" if debug else "warning",
    )
    server = uvicorn.Server(uv_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    _wait_for_server(base_url, timeout=10)

    window = webview.create_window(
        "CurioPilot",
        base_url,
        width=1200,
        height=800,
        min_size=(900, 600),
    )

    webview.start(debug=debug, user_agent=DESKTOP_BROWSER_USER_AGENT)

    server.should_exit = True
    server_thread.join(timeout=5)
    log.info("CurioPilot desktop exited")


def _wait_for_server(base_url: str, timeout: float = 10) -> None:
    """Poll the server until it responds or timeout is reached."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urlopen(f"{base_url}/api/run/status", timeout=2)
            return
        except (URLError, OSError):
            time.sleep(0.2)
    log.warning("Server did not become ready within %ss", timeout)
