from contextlib import asynccontextmanager
from pathlib import Path

from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import cinema as cinema_service
from server import library as library_service
from server import screen_capture
from server import web_input
from server.system_stats import gather_stats
from server.config import DEFAULT_HOST, DEFAULT_PORT, IPAD_HEIGHT, IPAD_WIDTH, QUALITY_PRESETS
from server.network import list_local_ips, preferred_ip
from server.settings import apply_preset, load_config, save_capture, save_config
from server.web_auth import COOKIE, COOKIE_MAX_AGE, WebAuth
from server.window_info import list_windows

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    screen_capture.engine.start()
    yield
    screen_capture.engine.stop()


app = FastAPI(title="iPad Monitor", version="1.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
auth = WebAuth()


def _session(request: Request) -> str | None:
    # Cookie o ?k=: los enlaces de video y descarga que se abren en VLC o iBooks
    # no llevan la cookie de Safari.
    return request.cookies.get(COOKIE) or request.query_params.get("k")


@app.middleware("http")
async def require_pin(request: Request, call_next):
    path = request.url.path
    if not auth.is_public(path) and not auth.valid(_session(request)):
        if path.startswith("/api/") or request.method != "GET" or "text/html" not in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Falta el PIN"}, status_code=401)
        return RedirectResponse("/login?next=" + quote(path), status_code=303)
    # Las órdenes llevan una cabecera propia: otra página no puede enviarla sin
    # permiso CORS, así que no puede mover el puntero ni escribir desde otro sitio.
    if request.method == "POST" and request.headers.get("x-requested-with") != "ipad-monitor":
        return JSONResponse({"detail": "Solicitud rechazada"}, status_code=403)
    return await call_next(request)


def _with_session(data, request: Request):
    """Agrega ?k= a las URL de archivos para abrirlas fuera de Safari."""
    token = _session(request)
    if isinstance(data, list):
        return [_with_session(item, request) for item in data]
    if not isinstance(data, dict) or not token:
        return data
    out = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = _with_session(value, request)
        elif key.endswith("url") and isinstance(value, str) and value.startswith(("/cinema/", "/library/")):
            value += ("&" if "?" in value else "?") + "k=" + quote(token)
        out[key] = value
    return out


class CaptureUpdate(BaseModel):
    monitor: int | None = None
    left: int | None = None
    top: int | None = None
    width: int | None = None
    height: int | None = None
    target_width: int | None = None
    target_height: int | None = None
    full_monitor: bool | None = None
    fit_mode: str | None = None
    mode: str | None = None
    hwnd: int | None = None


class WindowUpdate(BaseModel):
    hwnd: int


class PresetUpdate(BaseModel):
    preset: str


class PointerMove(BaseModel):
    dx: float = Field(description="Desplazamiento horizontal normalizado (-1 a 1)")
    dy: float = Field(description="Desplazamiento vertical normalizado (-1 a 1)")


class PointerClick(BaseModel):
    button: str = "left"


class MoveToEvent(BaseModel):
    x: float = Field(description="Posición horizontal relativa dentro de la imagen (0 a 1)")
    y: float = Field(description="Posición vertical relativa dentro de la imagen (0 a 1)")


class ScrollEvent(BaseModel):
    amount: int = Field(default=3, ge=-20, le=20)


class ZoomEvent(BaseModel):
    amount: int = Field(default=3, ge=-20, le=20)


class KeyEvent(BaseModel):
    key: str


class TypeEvent(BaseModel):
    text: str = Field(max_length=120)


class PinLogin(BaseModel):
    pin: str = Field(min_length=1, max_length=12)


class HotkeyEvent(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=5)


def _page(name: str) -> HTMLResponse:
    return HTMLResponse((STATIC / name).read_text(encoding="utf-8"))


@app.get("/login", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    return _page("login.html")


@app.post("/api/login")
def api_login(event: PinLogin, request: Request) -> JSONResponse:
    address = request.client.host if request.client else "?"
    if auth.locked(address):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Esperá un minuto.")
    token = auth.login(address, event.pin)
    if not token:
        raise HTTPException(status_code=403, detail="PIN incorrecto")
    print(f"{address}: navegador autorizado con el PIN", flush=True)
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE, token, max_age=COOKIE_MAX_AGE, path="/", samesite="strict")
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return _page("index.html")


@app.get("/mirror", response_class=HTMLResponse)
def mirror_page() -> HTMLResponse:
    return _page("mirror.html")


@app.get("/kiosk", response_class=HTMLResponse)
def kiosk_page() -> HTMLResponse:
    return _page("kiosk.html")


@app.get("/start", response_class=HTMLResponse)
def start_page() -> HTMLResponse:
    return _page("index.html")


@app.get("/touchpad", response_class=HTMLResponse)
def touchpad_page() -> HTMLResponse:
    return _page("touchpad.html")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> HTMLResponse:
    return _page("dashboard.html")


@app.get("/setup", response_class=HTMLResponse)
def setup_page() -> HTMLResponse:
    return _page("setup.html")


@app.get("/library", response_class=HTMLResponse)
def library_page() -> HTMLResponse:
    return _page("library.html")


@app.get("/api/library")
def api_library(request: Request) -> dict:
    return _with_session(library_service.list_books(), request)


@app.get("/library/download/{filename}")
def library_download(filename: str) -> FileResponse:
    path = library_service.resolve_book(filename)
    return FileResponse(
        path,
        media_type=library_service.mime_type(path),
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/cinema", response_class=HTMLResponse)
def cinema_page() -> HTMLResponse:
    return _page("cinema.html")


@app.get("/cinema/watch/{filename}", response_class=HTMLResponse)
def cinema_watch_page(filename: str) -> HTMLResponse:
    cinema_service.resolve_video(filename)
    return _page("cinema-watch.html")


@app.get("/api/cinema")
def api_cinema(request: Request) -> dict:
    return _with_session(cinema_service.list_videos(), request)


@app.get("/api/cinema/{filename}")
def api_cinema_video(filename: str, request: Request) -> dict:
    return _with_session(cinema_service.video_info(filename), request)


@app.get("/cinema/stream/{filename}")
def cinema_stream(filename: str) -> FileResponse:
    path = cinema_service.resolve_video(filename)
    return FileResponse(
        path,
        media_type=cinema_service.video_mime(path),
        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"},
    )


@app.get("/cinema/download/{filename}")
def cinema_download(filename: str) -> FileResponse:
    path = cinema_service.resolve_video(filename)
    return FileResponse(
        path,
        media_type=cinema_service.video_mime(path),
        filename=path.name,
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Accept-Ranges": "bytes",
        },
    )


@app.get("/cinema/subs/{filename}")
def cinema_subs(filename: str) -> FileResponse:
    path = cinema_service.resolve_subtitle(filename)
    return FileResponse(path, media_type="text/vtt")


@app.get("/cinema/download-subs/{filename}")
def cinema_download_subs(filename: str) -> FileResponse:
    path = cinema_service.resolve_subtitle(filename)
    return FileResponse(
        path,
        media_type="text/vtt",
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/remote", response_class=HTMLResponse)
def remote_page() -> HTMLResponse:
    return _page("touchpad.html")


@app.get("/voice", response_class=HTMLResponse)
def voice_page() -> HTMLResponse:
    return _page("keyboard.html")


@app.get("/api/health")
def api_health() -> dict:
    info = screen_capture.engine.frame_info()
    return {
        "ok": True,
        "ready": bool(info.get("bytes")),
        "seq": info.get("seq", 0),
        "config_version": info.get("config_version", 0),
    }


@app.get("/api/info")
def api_info() -> dict:
    cfg = load_config()
    ip = preferred_ip()
    return {
        "name": "iPad Monitor",
        "version": "1.1.0",
        "ipad_resolution": {"width": IPAD_WIDTH, "height": IPAD_HEIGHT},
        "local_url": f"http://{ip}:{DEFAULT_PORT}",
        "local_ips": list_local_ips(),
        "capture": cfg["capture"],
        "mode": cfg["capture"].get("mode", "monitor"),
        "hwnd": cfg["capture"].get("hwnd"),
        "preset": cfg.get("preset"),
        "presets": list(QUALITY_PRESETS.keys()),
        "stream": {
            "jpeg_quality": cfg.get("jpeg_quality"),
            "target_fps": cfg.get("target_fps"),
            "stats": screen_capture.engine.stats(),
        },
        "monitors": screen_capture.list_monitors(),
        "config_version": cfg.get("config_version", 0),
    }


@app.get("/api/stats")
def api_stats() -> dict:
    return gather_stats()


@app.get("/api/monitors")
def api_monitors() -> list[dict]:
    return screen_capture.list_monitors()


@app.get("/api/capture")
def api_get_capture() -> dict:
    return load_config()["capture"]


@app.post("/api/capture")
def api_set_capture(update: CaptureUpdate) -> dict:
    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    return save_capture(payload)


@app.post("/api/capture/monitor/{monitor_id}")
def api_use_monitor(monitor_id: int) -> dict:
    if monitor_id <= 0:
        raise HTTPException(status_code=400, detail="Elegí un monitor válido (1, 2, 3...)")

    monitors = screen_capture.list_monitors()
    selected = next((m for m in monitors if m["id"] == monitor_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Monitor no encontrado")

    # Guardar resolución lógica (la que ves en Windows) para la UI; la captura usa mss en full_monitor.
    return save_capture(
        {
            "mode": "monitor",
            "monitor": monitor_id,
            "left": 0,
            "top": 0,
            "width": selected.get("logical_width") or selected["width"],
            "height": selected.get("logical_height") or selected["height"],
            "target_width": IPAD_WIDTH,
            "target_height": IPAD_HEIGHT,
            "full_monitor": True,
            "fit_mode": load_config()["capture"].get("fit_mode", "fill"),
        }
    )


@app.get("/api/windows")
def api_windows() -> list[dict]:
    return list_windows()


@app.post("/api/capture/window")
def api_use_window(update: WindowUpdate) -> dict:
    windows = list_windows()
    selected = next((w for w in windows if w["hwnd"] == update.hwnd), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Ventana no encontrada")

    return save_capture(
        {
            "mode": "window",
            "hwnd": update.hwnd,
            "monitor": 1,
            "left": selected["left"],
            "top": selected["top"],
            "width": selected["width"],
            "height": selected["height"],
            "target_width": IPAD_WIDTH,
            "target_height": IPAD_HEIGHT,
            "full_monitor": False,
            "fit_mode": load_config()["capture"].get("fit_mode", "fill"),
        }
    )


@app.get("/api/windows/{hwnd}/preview.jpg")
def window_preview(hwnd: int) -> Response:
    if hwnd <= 0:
        raise HTTPException(status_code=400, detail="Ventana inválida")
    return Response(
        content=screen_capture.capture_single_jpeg(hwnd=hwnd, preview=True),
        media_type="image/jpeg",
    )


@app.post("/api/fit/{mode}")
def api_set_fit(mode: str) -> dict:
    if mode not in ("fit", "fill", "stretch"):
        raise HTTPException(status_code=400, detail="Modo inválido: fit, fill o stretch")
    capture = save_capture({"fit_mode": mode})
    return {
        "ok": True,
        "fit_mode": capture.get("fit_mode"),
        "config_version": load_config().get("config_version"),
    }


@app.post("/api/preset")
def api_set_preset(update: PresetUpdate) -> dict:
    try:
        return apply_preset(update.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/monitors/{monitor_id}/preview.jpg")
def monitor_preview(monitor_id: int) -> Response:
    if monitor_id <= 0:
        raise HTTPException(status_code=400, detail="Monitor inválido")
    return Response(
        content=screen_capture.capture_single_jpeg(monitor_id=monitor_id, preview=True),
        media_type="image/jpeg",
    )


@app.get("/stream.mjpg")
def stream_mjpeg() -> StreamingResponse:
    return StreamingResponse(
        screen_capture.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/frame")
def api_frame() -> dict:
    screen_capture.engine.start()
    return screen_capture.engine.frame_info()


@app.get("/snapshot.jpg")
def snapshot() -> Response:
    frame = screen_capture.get_stream_jpeg()
    info = screen_capture.engine.frame_info()
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "X-Frame-Seq": str(info["seq"]),
    }
    return Response(content=frame, media_type="image/jpeg", headers=headers)


@app.post("/api/pointer/move")
def pointer_move(event: PointerMove) -> dict:
    web_input.move_rel(event.dx * 55, event.dy * 55)
    return {"ok": True}


@app.post("/api/pointer/click")
def pointer_click(event: PointerClick) -> dict:
    web_input.click("right" if event.button == "right" else "left")
    return {"ok": True}


@app.post("/api/pointer/move-to")
def pointer_move_to(event: MoveToEvent) -> dict:
    region = screen_capture.engine.last_region()
    abs_x = int(region["left"] + event.x * region["width"])
    abs_y = int(region["top"] + event.y * region["height"])
    web_input.move_to(abs_x, abs_y)
    return {"ok": True}


@app.post("/api/pointer/scroll")
def pointer_scroll(event: ScrollEvent) -> dict:
    web_input.scroll(event.amount)
    return {"ok": True}


@app.post("/api/pointer/zoom")
def pointer_zoom(event: ZoomEvent) -> dict:
    web_input.zoom(event.amount)
    return {"ok": True}


@app.get("/keyboard", response_class=HTMLResponse)
def keyboard_page() -> HTMLResponse:
    return _page("keyboard.html")


@app.post("/api/key")
def send_key(event: KeyEvent) -> dict:
    if event.key:
        web_input.press(event.key)
    return {"ok": True}


@app.post("/api/type")
def type_text(event: TypeEvent) -> dict:
    if event.text:
        web_input.write(event.text)
    return {"ok": True}


@app.post("/api/hotkey")
def send_hotkey(event: HotkeyEvent) -> dict:
    web_input.hotkey(event.keys)
    return {"ok": True}


@app.post("/api/media/{action}")
def media_action(action: str) -> dict:
    keys = {
        "playpause": "playpause",
        "next": "nexttrack",
        "prev": "prevtrack",
        "mute": "volumemute",
        "up": "volumeup",
        "down": "volumedown",
    }
    key = keys.get(action)
    if not key:
        raise HTTPException(status_code=400, detail="Acción desconocida")
    web_input.press(key)
    return {"ok": True}


def run() -> None:
    import uvicorn

    ip = preferred_ip()
    ips = list_local_ips()

    print("")
    print("  iPad Monitor — iPad Mini 1")
    print("  =====================")
    print("  Abre Safari en el iPad (misma Wi‑Fi, sin VPN) y visita:")
    print(f"  http://{ip}:{DEFAULT_PORT}")
    print("")
    print(f"  >>> PIN: {auth.pin} <<<   (se pide una sola vez en cada navegador)")
    print("")
    print("  IMPORTANTE: el servidor debe escuchar en 0.0.0.0 (todas las interfaces).")
    print("  No uses --host 127.0.0.1 o el iPad no podrá conectarse.")
    if len(ips) > 1:
        print("")
        print("  Otras IPs detectadas:")
        for alt in ips:
            if alt != ip:
                print(f"  http://{alt}:{DEFAULT_PORT}")
    print("")
    print("  iPad — inicio rápido: /start")
    print("  iPad — espejo fijo:     /kiosk")
    print("  iPad — biblioteca:      /library")
    print("  iPad — cine:            /cinema")
    print("  Libros en PC:           library/  (.epub / .pdf)")
    print("  Videos en PC:           library/videos/  (.mp4 + .vtt)")
    print("  Configuración:          /setup")
    print("")

    uvicorn.run("server.main:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    run()
