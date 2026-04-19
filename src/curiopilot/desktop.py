"""PyWebView desktop launcher for CurioPilot."""

from __future__ import annotations

import json
import logging
import os
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
_READER_GEOMETRY_PATH = Path.home() / ".curiopilot" / "reader_window.json"
_APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "app.ico"

_READER_DEFAULT_WIDTH = 1100
_READER_DEFAULT_HEIGHT = 850
_READER_MIN_WIDTH = 600
_READER_MIN_HEIGHT = 400


def _windows_dpi_scale() -> float:
    """Return the primary display's DPI scale factor (e.g. 1.0, 1.25, 1.5).

    pywebview on Windows/EdgeChromium reports `moved`/`resized` events and
    reads Form.Location in *physical* pixels, but `create_window(x=, y=,
    width=, height=)` expects *logical* pixels and multiplies internally.
    We divide saved values by this factor so saves and loads round-trip.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes

        return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
    except Exception:
        return 1.0


def _load_reader_geometry() -> dict | None:
    """Load saved reader window geometry, or None if missing/invalid."""
    try:
        if not _READER_GEOMETRY_PATH.is_file():
            return None
        data = json.loads(_READER_GEOMETRY_PATH.read_text(encoding="utf-8"))
        x = int(data["x"])
        y = int(data["y"])
        width = int(data["width"])
        height = int(data["height"])
        if width < _READER_MIN_WIDTH or height < _READER_MIN_HEIGHT:
            return None
        if not (-10000 < x < 20000 and -10000 < y < 20000):
            return {"width": width, "height": height}
        return {"x": x, "y": y, "width": width, "height": height}
    except Exception:
        log.debug("Failed to load reader window geometry", exc_info=True)
        return None


def _save_reader_geometry(geom: dict) -> None:
    """Atomically write reader window geometry to disk."""
    try:
        _READER_GEOMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _READER_GEOMETRY_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(geom), encoding="utf-8")
        os.replace(tmp, _READER_GEOMETRY_PATH)
    except Exception:
        log.debug("Failed to save reader window geometry", exc_info=True)


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
        self._pending_geometry: dict | None = None
        self._save_timer: threading.Timer | None = None

    def _schedule_geometry_save(self) -> None:
        if self._save_timer is not None:
            self._save_timer.cancel()
        timer = threading.Timer(0.5, self._flush_geometry)
        timer.daemon = True
        self._save_timer = timer
        timer.start()

    def _flush_geometry(self) -> None:
        with self._lock:
            geom = self._pending_geometry
        if geom is not None:
            _save_reader_geometry(geom)

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
                saved = _load_reader_geometry()
                create_kwargs: dict = dict(
                    width=saved.get("width", _READER_DEFAULT_WIDTH) if saved else _READER_DEFAULT_WIDTH,
                    height=saved.get("height", _READER_DEFAULT_HEIGHT) if saved else _READER_DEFAULT_HEIGHT,
                    min_size=(_READER_MIN_WIDTH, _READER_MIN_HEIGHT),
                )
                if saved and "x" in saved and "y" in saved:
                    create_kwargs["x"] = saved["x"]
                    create_kwargs["y"] = saved["y"]

                new_win = webview.create_window(
                    display_title,
                    url,
                    **create_kwargs,
                )
                self._reader_window = new_win
                if saved:
                    self._pending_geometry = dict(saved)
                _schedule_window_icon(display_title)

                scale = _windows_dpi_scale() or 1.0

                def _logical(v) -> int:
                    return int(round(float(v) / scale))

                def _on_closed():
                    with self._lock:
                        if self._reader_window is new_win:
                            self._reader_window = None
                        timer = self._save_timer
                        self._save_timer = None
                        try:
                            geom = {
                                "x": _logical(new_win.x),
                                "y": _logical(new_win.y),
                                "width": _logical(new_win.width),
                                "height": _logical(new_win.height),
                            }
                            self._pending_geometry = geom
                        except Exception:
                            geom = self._pending_geometry
                    if timer is not None:
                        timer.cancel()
                    if geom is not None:
                        _save_reader_geometry(geom)
                    log.debug("Reader window closed")

                def _on_loaded():
                    log.info("Reader window loaded URL successfully")

                def _on_moved(x, y):
                    with self._lock:
                        base = dict(self._pending_geometry) if self._pending_geometry else {}
                        base.update({"x": _logical(x), "y": _logical(y)})
                        try:
                            base.setdefault("width", _logical(new_win.width))
                            base.setdefault("height", _logical(new_win.height))
                        except Exception:
                            pass
                        self._pending_geometry = base
                    self._schedule_geometry_save()

                def _on_resized(width, height):
                    with self._lock:
                        base = dict(self._pending_geometry) if self._pending_geometry else {}
                        base.update({"width": _logical(width), "height": _logical(height)})
                        try:
                            base.setdefault("x", _logical(new_win.x))
                            base.setdefault("y", _logical(new_win.y))
                        except Exception:
                            pass
                        self._pending_geometry = base
                    self._schedule_geometry_save()

                new_win.events.closed += _on_closed
                new_win.events.loaded += _on_loaded
                try:
                    new_win.events.moved += _on_moved
                except AttributeError:
                    log.debug("pywebview build lacks 'moved' event")
                try:
                    new_win.events.resized += _on_resized
                except AttributeError:
                    log.debug("pywebview build lacks 'resized' event")

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
