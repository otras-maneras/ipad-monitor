# Modo web

El modo web no necesita jailbreak: se usa desde Safari de iOS 9. Ofrece espejo de pantalla por JPEG, touchpad, teclado, estadísticas de la PC, una biblioteca de libros y un cine. Tiene más demora que el visor nativo (entre 100 y 300 ms), así que sirve mejor para control, lectura y referencias que como monitor.

## Arrancar

**Linux:**

```bash
.venv-linux/bin/python run.py
```

`install-linux.sh` instala lo necesario. El control del puntero y el teclado usa XTest, como el emisor nativo.

**Windows:** doble clic en `run.bat`, que crea `.venv` si falta e instala `requirements.txt`.

La consola muestra la dirección (`http://IP_DE_LA_PC:8765/`) y un **PIN**. En Safari del iPad, abrí la dirección e ingresá el PIN. Cada navegador lo pide una sola vez: la sesión se guarda en `~/.config/ipad-monitor/web-sesiones.json` (en Windows, `%APPDATA%\ipad-monitor\`) y sobrevive a los reinicios. Los accesos de la pantalla de inicio de iOS tienen su propio almacén, así que piden el PIN una vez más. Para revocar todas las sesiones, borrá ese archivo.

## Páginas

| URL | Función |
|---|---|
| `/`, `/start` | Inicio: estado, estadísticas y accesos |
| `/kiosk` | Espejo a pantalla completa. Tres toques abajo a la izquierda abren el menú; abajo a la derecha cambian el ajuste. |
| `/mirror` | Espejo con estadísticas y ajuste `fill`, `fit` o `stretch` |
| `/setup` | Monitor, ventana (solo Windows), calidad y vistas previas |
| `/touchpad`, `/remote` | Touchpad, clic, arrastre, zoom, scroll y multimedia |
| `/keyboard`, `/voice` | Teclado y dictado de iOS |
| `/dashboard` | Estadísticas de la PC |
| `/library` | Libros de `library/` (EPUB, PDF) para abrir en iBooks |
| `/cinema` | Videos de `library/videos/` (MP4 y subtítulos VTT), en streaming o para VLC |
| `/login` | PIN |

En Safari → Compartir → **Agregar a pantalla de inicio** se crean accesos directos a cualquier página.

## Seguridad

- Sin sesión, las páginas llevan a `/login` y la API responde 401. Cinco PIN incorrectos bloquean esa IP durante un minuto.
- Las órdenes (`POST`) exigen la cabecera `X-Requested-With: ipad-monitor`, que otra página no puede enviar sin permiso CORS. Así un sitio malicioso abierto en otro dispositivo de la red no puede mover el puntero ni escribir.
- Los enlaces de video y libros llevan la sesión en `?k=`, porque VLC e iBooks abren la URL sin la cookie de Safari. Tratá esos enlaces como privados.
- El tráfico es HTTP sin cifrar dentro de la red local. Usalo solo en redes de confianza.

## Espejo

`static/mirror-core.js` consulta `GET /api/frame` cada 100 ms (kiosco) o 150 ms (espejo) y, cuando cambia el número de cuadro, carga `/snapshot.jpg`. Se usa polling y no MJPEG porque Safari de iOS 9 deja la pantalla negra con MJPEG en `<img>`. En el servidor, `server/screen_capture.py` captura en un hilo propio al ritmo del preset, ajusta a 1024×768 y guarda el último JPEG.

| Preset | Calidad JPEG | FPS objetivo |
|---|---|---|
| `ultra` | 30 | 12 |
| `turbo` | 38 | 16 |
| `balanced` | 52 | 12 |
| `quality` | 68 | 10 |

Los ajustes se guardan en `config.json`, que se crea desde `config.example.json`. Si el monitor guardado ya no existe, se usa el 1.

## API

Todas las rutas requieren sesión salvo `/login` y `POST /api/login` (`{"pin": "1234"}`).

| Endpoint | Método | Función |
|---|---|---|
| `/api/info`, `/api/health`, `/api/stats` | GET | Estado, salud y estadísticas de la PC |
| `/api/frame`, `/snapshot.jpg` | GET | Datos del cuadro actual y la imagen JPEG |
| `/api/monitors`, `/api/monitors/{id}/preview.jpg` | GET | Monitores y vista previa |
| `/api/capture`, `/api/capture/monitor/{id}` | GET, POST | Región de captura y monitor |
| `/api/windows`, `/api/capture/window` | GET, POST | Captura de una ventana (solo Windows) |
| `/api/fit/{mode}`, `/api/preset` | POST | Ajuste y calidad |
| `/api/pointer/move`, `move-to`, `click`, `scroll`, `zoom` | POST | Puntero |
| `/api/key`, `/api/type`, `/api/hotkey`, `/api/media/{acción}` | POST | Teclado y multimedia |
| `/api/library`, `/library/download/{archivo}` | GET | Libros |
| `/api/cinema`, `/cinema/stream/{archivo}`, `/cinema/download/{archivo}`, `/cinema/subs/{archivo}` | GET | Videos y subtítulos |

## Código

| Archivo | Función |
|---|---|
| `server/main.py` | Rutas, API y PIN |
| `server/web_auth.py` | PIN, sesiones y bloqueo por intentos |
| `server/web_input.py` | Puntero y teclado: PyAutoGUI en Windows, XTest en Linux |
| `server/screen_capture.py` | Captura y JPEG |
| `server/library.py`, `server/cinema.py` | Biblioteca y cine |
| `static/` | Páginas HTML y JS sin frameworks, con `XMLHttpRequest`, compatibles con Safari de iOS 9 |
