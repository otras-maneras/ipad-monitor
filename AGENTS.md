# iPad Monitor — guía para agentes

Antes de cambiar código o documentación, leé el [README](README.md), [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) y [docs/HISTORIA.md](docs/HISTORIA.md). Si existe `docs/privado/CONTEXTO.md` (fuera de git), es el diario de trabajo local con el estado más reciente: leelo y mantenelo al día.

## Estado

- Visor nativo 0.3.1 (Objective‑C, iOS 9, ARMv7) y emisor H.264 para Linux/X11 y Windows, por Wi‑Fi y USB, con controles. La 0.3.0 se probó en un iPad Mini 1; la 0.3.1 solo cambia el nombre visible y no se probó en el iPad.
- Linux (Xubuntu, XFCE/X11) es la plataforma de referencia: pantalla extendida con `VIRTUAL1` del driver `intel`, instalador `install-linux.sh` y lanzador `scripts/linux/ipad-monitor.sh`.
- Windows: `install-windows.bat` y `scripts/windows/ipad-monitor.ps1`, sin probar en Windows.
- Modo web (FastAPI + Safari iOS 9) con PIN, en Linux y Windows. En Windows no se probó después de agregar el PIN y la capa `server/web_input.py`.

## Reglas

- **Prioridad:** el rendimiento como monitor externo por Wi‑Fi. Antes de cambiar el emisor o el visor, comprobá que el cambio no suma tráfico, demora ni congelamientos en ese modo, y medilo en la PC cuando se pueda.
- Frontend compatible con **Safari de iOS 9**: `XMLHttpRequest`, sin `fetch` ni sintaxis moderna. Toda orden `POST` va por `MiniPad.post` de `static/app.js`, que agrega la cabecera que exige el servidor.
- Servidor web en **0.0.0.0:8765**; emisor por Wi‑Fi en la IP LAN y el puerto 8767; USB al puerto 8769 del iPad.
- Espejo web por polling de `/api/frame` y `/snapshot.jpg`; no depender de MJPEG en iOS 9.
- El visor se compila en Linux con Theos según [native/COMPILAR.md](native/COMPILAR.md). Un cambio en `native/ios/` queda sin verificar hasta compilarlo e instalarlo, y hay que decirlo.
- Al cambiar `native/`, subir la versión en `native/ios/control` y en `Info.plist` (`CFBundleShortVersionString` y `CFBundleVersion`). No cambiar el identificador `com.minipad.ipadscreenh264`: es el que permite actualizar.
- Emisor y visor deben entenderse entre versiones: cada lado ignora los mensajes que no conoce.
- Un emisor abierto sigue con el código anterior: después de cambiar `server/ipadscreen*.py` hay que reiniciarlo.
- Las pruebas de entrada mueven el cursor real y pueden hacer clic. Usá movimientos mínimos que se deshagan y no envíes teclas ni clics de prueba.
- Commits solo si quien mantiene el proyecto lo pide. Repositorio público: `otras-maneras/ipad-monitor`, rama `main`.

## Docs

- [README.md](README.md) — instalación y uso
- [native/README.md](native/README.md) — visor y emisor
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — protocolo, codificación y demora
- [docs/WEB.md](docs/WEB.md) — modo web y API
- [docs/IPAD.md](docs/IPAD.md) — preparar el iPad
- [native/COMPILAR.md](native/COMPILAR.md) — compilar el visor
- [docs/HISTORIA.md](docs/HISTORIA.md) — historia y mediciones
