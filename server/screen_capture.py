import io
import threading
import time
from typing import Iterator

import mss
from PIL import Image, ImageDraw

from server.config import IPAD_HEIGHT, IPAD_WIDTH, JPEG_QUALITY, TARGET_FPS
from server.cursor_overlay import draw_cursor
from server.monitor_info import enrich_monitor
from server.settings import load_config
from server.window_info import get_window_rect, is_window_valid

RESIZE = Image.Resampling.NEAREST


def list_monitors() -> list[dict[str, int | str | bool]]:
    with mss.mss() as sct:
        monitors: list[dict[str, int | str | bool]] = []
        for index, mon in enumerate(sct.monitors):
            if index == 0:
                label = "Todos (virtual)"
                entry = {
                    "id": index,
                    "label": label,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                    "logical_width": mon["width"],
                    "logical_height": mon["height"],
                    "scale_percent": 100,
                }
            else:
                meta = enrich_monitor(mon)
                lw = int(meta["logical_width"])
                lh = int(meta["logical_height"])
                scale = int(meta.get("scale_percent") or 100)
                label = f"Monitor {index} — {lw}×{lh}"
                if scale > 100:
                    label += f" ({scale}%)"
                entry = {
                    "id": index,
                    "label": label,
                    "left": meta["left"],
                    "top": meta["top"],
                    "width": meta["width"],
                    "height": meta["height"],
                    "logical_width": lw,
                    "logical_height": lh,
                    "scale_percent": scale,
                }
                if "is_primary" in meta:
                    entry["is_primary"] = bool(meta["is_primary"])
            monitors.append(entry)
        return monitors


def _monitor_region(capture: dict, sct: mss.mss) -> dict[str, int]:
    if capture.get("mode") == "window":
        hwnd = int(capture.get("hwnd") or 0)
        if hwnd and is_window_valid(hwnd):
            rect = get_window_rect(hwnd)
            if rect:
                return {
                    "left": rect["left"],
                    "top": rect["top"],
                    "width": rect["width"],
                    "height": rect["height"],
                }
        # fallback a la región guardada si la ventana no está disponible
        return {
            "left": int(capture.get("left", 0)),
            "top": int(capture.get("top", 0)),
            "width": int(capture.get("width", IPAD_WIDTH)),
            "height": int(capture.get("height", IPAD_HEIGHT)),
        }

    monitor_index = int(capture.get("monitor", 1))
    if monitor_index >= len(sct.monitors):
        # El monitor guardado ya no existe (se desconectó o cambió la numeración).
        monitor_index = 1
    if capture.get("full_monitor") and monitor_index > 0:
        mon = sct.monitors[monitor_index]
        return {
            "left": int(mon["left"]),
            "top": int(mon["top"]),
            "width": int(mon["width"]),
            "height": int(mon["height"]),
        }
    region = {
        "left": int(capture["left"]),
        "top": int(capture["top"]),
        "width": int(capture["width"]),
        "height": int(capture["height"]),
    }
    if monitor_index > 0:
        mon = sct.monitors[monitor_index]
        region = {
            "left": mon["left"] + region["left"],
            "top": mon["top"] + region["top"],
            "width": region["width"],
            "height": region["height"],
        }
    return region


def _fit_to_ipad(image: Image.Image, fit_mode: str, canvas: Image.Image | None = None) -> Image.Image:
    """Escala siempre a 1024×768 (píxeles nativos del iPad Mini 1)."""
    target_w, target_h = IPAD_WIDTH, IPAD_HEIGHT
    src_w, src_h = image.size

    if src_w == target_w and src_h == target_h:
        return image

    if fit_mode == "stretch":
        return image.resize((target_w, target_h), RESIZE)

    if fit_mode == "fill":
        scale = max(target_w / src_w, target_h / src_h)
        new_w = max(int(src_w * scale), 1)
        new_h = max(int(src_h * scale), 1)
        resized = image.resize((new_w, new_h), RESIZE)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    # fit — contenido completo, centrado
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(int(src_w * scale), 1)
    new_h = max(int(src_h * scale), 1)
    resized = image.resize((new_w, new_h), RESIZE)
    if canvas is not None:
        ImageDraw.Draw(canvas).rectangle((0, 0, target_w, target_h), fill=(0, 0, 0))
        canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
        return canvas
    out = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    out.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return out


def _encode_jpeg(image: Image.Image, quality: int, subsample: int, buffer: io.BytesIO) -> bytes:
    buffer.seek(0)
    buffer.truncate(0)
    image.save(buffer, format="JPEG", quality=quality, optimize=False, progressive=False, subsampling=subsample)
    return buffer.getvalue()


class StreamEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest = b""
        self._sequence = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._frames = 0
        self._started_at = 0.0
        self._last_capture_ms = 0.0
        self._source_width = 0
        self._source_height = 0
        self._fit_mode = "fill"
        self._config_version = 0
        self._last_region = {"left": 0, "top": 0, "width": IPAD_WIDTH, "height": IPAD_HEIGHT}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._started_at = time.perf_counter()
        self._thread = threading.Thread(target=self._capture_loop, name="ipad-monitor-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _capture_loop(self) -> None:
        sct = mss.mss()
        jpeg_buffer = io.BytesIO()
        canvas = Image.new("RGB", (IPAD_WIDTH, IPAD_HEIGHT), (0, 0, 0))
        cfg_version = -1
        cfg: dict = {}
        capture: dict = {}
        quality = JPEG_QUALITY
        subsample = 2
        fit_mode = "fill"
        fps = TARGET_FPS

        while self._running:
            fresh = load_config()
            if fresh.get("config_version", 0) != cfg_version:
                cfg = fresh
                capture = cfg["capture"]
                quality = int(cfg.get("jpeg_quality") or JPEG_QUALITY)
                subsample = int(cfg.get("jpeg_subsample") or 2)
                fit_mode = capture.get("fit_mode") or "fill"
                fps = max(int(cfg.get("target_fps") or TARGET_FPS), 1)
                cfg_version = int(cfg.get("config_version") or 0)

            delay = 1.0 / fps
            started = time.perf_counter()

            try:
                region = _monitor_region(capture, sct)
                if capture.get("mode") == "window":
                    # guardar la última región conocida para fallback
                    capture["left"] = region["left"]
                    capture["top"] = region["top"]
                    capture["width"] = region["width"]
                    capture["height"] = region["height"]
                self._last_region = region
                shot = sct.grab(region)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
                image = draw_cursor(image, region)
                source_w, source_h = image.size
                if fit_mode == "fit":
                    image = _fit_to_ipad(image, fit_mode, canvas)
                else:
                    image = _fit_to_ipad(image, fit_mode)
                frame = _encode_jpeg(image, quality, subsample, jpeg_buffer)
                elapsed_ms = (time.perf_counter() - started) * 1000
                with self._lock:
                    if frame:
                        self._latest = frame
                        self._sequence += 1
                        self._frames += 1
                        self._last_capture_ms = round(elapsed_ms, 1)
                        self._source_width = source_w
                        self._source_height = source_h
                        self._fit_mode = fit_mode
                        self._config_version = cfg_version
            except Exception:
                time.sleep(0.05)
                continue

            remaining = delay - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)

    def latest_frame(self) -> bytes:
        with self._lock:
            return self._latest

    def frame_info(self) -> dict[str, int | float | str]:
        with self._lock:
            elapsed = max(time.perf_counter() - self._started_at, 0.001)
            return {
                "seq": self._sequence,
                "bytes": len(self._latest),
                "fps_actual": round(self._frames / elapsed, 1),
                "capture_ms": self._last_capture_ms,
                "fit_mode": self._fit_mode,
                "config_version": self._config_version,
                "source_width": self._source_width,
                "source_height": self._source_height,
                "output_width": IPAD_WIDTH,
                "output_height": IPAD_HEIGHT,
            }

    def stats(self) -> dict[str, float | int]:
        info = self.frame_info()
        return {
            "frames": self._frames,
            "fps_actual": info["fps_actual"],
            "frame_bytes": info["bytes"],
            "capture_ms": info["capture_ms"],
            "sequence": info["seq"],
        }

    def last_region(self) -> dict[str, int]:
        with self._lock:
            return dict(self._last_region)


engine = StreamEngine()


def get_stream_jpeg() -> bytes:
    engine.start()
    frame = engine.latest_frame()
    if frame:
        return frame
    return capture_single_jpeg()


def mjpeg_stream() -> Iterator[bytes]:
    engine.start()
    while True:
        frame = engine.latest_frame()
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(0.08)


def capture_single_jpeg(
    monitor_id: int | None = None,
    preview: bool = False,
    hwnd: int | None = None,
    *,
    output_size: tuple[int, int] = (IPAD_WIDTH, IPAD_HEIGHT),
    jpeg_quality: int | None = None,
) -> bytes:
    cfg = load_config()
    capture = dict(cfg["capture"])
    if hwnd is not None and hwnd > 0:
        capture["mode"] = "window"
        capture["hwnd"] = hwnd
    elif monitor_id is not None and monitor_id > 0:
        capture["monitor"] = monitor_id
        capture["full_monitor"] = True
        capture["mode"] = "monitor"

    fit_mode = capture.get("fit_mode") or "fill"
    quality = jpeg_quality if jpeg_quality is not None else int(cfg.get("jpeg_quality") or JPEG_QUALITY)
    subsample = int(cfg.get("jpeg_subsample") or 2)

    with mss.mss() as sct:
        region = _monitor_region(capture, sct)
        shot = sct.grab(region)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        if not preview:
            image = draw_cursor(image, region)

    if preview:
        image.thumbnail((480, 360), RESIZE)
    else:
        image = _fit_to_ipad(image, fit_mode)
        if image.size != output_size:
            image = image.resize(output_size, Image.Resampling.BILINEAR)

    return _encode_jpeg(image, quality, subsample, io.BytesIO())
