"""PyWebView desktop launcher for CurioPilot."""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)

DESKTOP_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

_STORAGE_DIR = Path.home() / ".curiopilot" / "webview_data"
_APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "app.ico"


def _schedule_window_icon(title: str) -> None:
    """Apply the packaged CurioPilot icon to a native Windows window."""
    if sys.platform != "win32" or not _APP_ICON_PATH.is_file():
        return

    threading.Thread(target=_apply_window_icon_when_ready, args=(title,), daemon=True).start()


def _apply_window_icon_when_ready(title: str, timeout: float = 5.0) -> None:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        image_icon = 1
        lr_loadfromfile = 0x0010
        lr_defaultsize = 0x0040
        wm_seticon = 0x0080
        icon_small = 0
        icon_big = 1
        gclp_hicon = -14
        gclp_hiconsm = -34

        icon_handle = user32.LoadImageW(
            None,
            str(_APP_ICON_PATH),
            image_icon,
            0,
            0,
            lr_loadfromfile | lr_defaultsize,
        )
        if not icon_handle:
            return

        set_class_long = getattr(user32, "SetClassLongPtrW", None)
        if set_class_long is None:
            set_class_long = user32.SetClassLongW

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.SendMessageW(hwnd, wm_seticon, icon_small, icon_handle)
                user32.SendMessageW(hwnd, wm_seticon, icon_big, icon_handle)
                set_class_long(hwnd, gclp_hicon, icon_handle)
                set_class_long(hwnd, gclp_hiconsm, icon_handle)
                return
            time.sleep(0.1)
    except Exception:
        log.debug("Unable to apply window icon for %r", title, exc_info=True)


class _ReaderBridge:
    """Manages a single reusable pywebview Reader window.

    All pywebview window operations (create_window, load_url, show, restore)
    are safe to call from non-GUI threads during the GUI loop — pywebview
    handles internal dispatch.  We add explicit try/except + logging so
    failures are never silent.
    """

    def __init__(self) -> None:
        self._reader_window = None
        self._lock = threading.Lock()

    def open_reader(self, url: str, title: str | None = None) -> tuple[bool, str]:
        """Open *url* in the reader window.

        Returns ``(success, reason)`` where *reason* is one of:
        ``opened_ok``, ``navigated_ok``, ``reader_open_failed``.
        """
        import webview

        display_title = title or "Reader"
        log.info("open_reader requested: url=%s title=%r", url, display_title)

        with self._lock:
            win = self._reader_window

            if win is not None:
                try:
                    win.load_url(url)
                    win.title = display_title
                    win.show()
                    win.restore()
                    log.info("Navigated existing reader window to %s", url)
                    return True, "navigated_ok"
                except Exception:
                    log.warning(
                        "Existing reader window unusable, will recreate",
                        exc_info=True,
                    )
                    self._reader_window = None

            try:
                new_win = webview.create_window(
                    display_title,
                    url,
                    width=1100,
                    height=850,
                    min_size=(600, 400),
                )
                self._reader_window = new_win
                _schedule_window_icon(display_title)

                def _on_closed():
                    with self._lock:
                        if self._reader_window is new_win:
                            self._reader_window = None
                    log.debug("Reader window closed")

                def _on_loaded():
                    log.info("Reader window loaded URL successfully")

                new_win.events.closed += _on_closed
                new_win.events.loaded += _on_loaded

                log.info("Created new reader window for %s", url)
                return True, "opened_ok"
            except Exception:
                log.exception("Failed to create reader window for %s", url)
                self._reader_window = None
                return False, "reader_open_failed"


def launch_app(
    config_path: str | Path = "config.yaml",
    port: int = 19231,
    debug: bool = False,
) -> None:
    """Launch CurioPilot as a native desktop window."""
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
    _schedule_window_icon("CurioPilot")

    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    start_kwargs: dict = dict(
        debug=debug,
        user_agent=DESKTOP_BROWSER_USER_AGENT,
        private_mode=False,
        storage_path=str(_STORAGE_DIR),
    )

    if sys.platform == "win32":
        start_kwargs["gui"] = "edgechromium"

    webview.start(**start_kwargs)

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
