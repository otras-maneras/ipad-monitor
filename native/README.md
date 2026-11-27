# iPad Monitor — visor y emisor

El **visor** es la app del iPad (Objective‑C, iOS 9, ARMv7). Deriva de [iPadScreen v1.0.2](https://github.com/demirfirat/ipadScreen/tree/v1.0.2) y conserva su licencia MIT. Se instala como `/Applications/IPadScreenH264.app` con el identificador `com.minipad.ipadscreenh264`, que se mantiene para que cada versión se instale como actualización de la anterior.

El **emisor** es `server/ipadscreen_h264.py`: captura una pantalla de la PC con FFmpeg, la codifica en H.264 y la envía al visor por Wi‑Fi (TCP 8767) o USB (puerto 8769 del iPad). Funciona en Linux/X11 y en Windows.

Los lanzadores (`install-linux.sh` e `install-windows.bat`, ver el [README](../README.md)) arrancan el emisor solos. Esta guía explica qué hacen y cómo usarlo a mano.

## Arrancar el emisor a mano

Desde la raíz del proyecto, con el entorno de Python ya creado:

```bash
# Linux
.venv-linux/bin/python -B -m server.ipadscreen_h264 --bind IP_DE_LA_PC --usb --monitor 2
```

```powershell
# Windows
.\.venv\Scripts\python.exe -B -m server.ipadscreen_h264 --bind IP_DE_LA_PC --usb --monitor 2
```

| Opción | Efecto |
|---|---|
| `--bind IP` | Atiende por Wi‑Fi en esa IP de la PC (`ip -br addr` en Linux, `ipconfig` en Windows). |
| `--usb` | Atiende por cable. Con `--bind` también, el modo se elige en el panel del visor. |
| `--monitor N` | Pantalla que se transmite. La de 1024×768 se ve sin escalar; otras se ajustan con bandas. |
| `--calidad nitida` o `fluida` | Calidad inicial. El visor la cambia desde el panel. |
| `--refresco intra` o `clave` | `intra` (predeterminado en Linux) renueva la imagen por franjas, sin picos de tráfico. `clave` manda un cuadro clave cada 2 s (predeterminado en Windows). |
| `--preset` | Preset de x264. El predeterminado es `superfast`. |

Un emisor abierto sigue con el código con el que arrancó: después de actualizar el proyecto hay que cerrarlo y volver a abrirlo.

### Emparejamiento

La primera vez, el visor pide el PIN de 4 cifras que muestra el emisor. Después, el emisor recuerda al iPad en `~/.config/ipad-monitor/ipadscreen-claves.json` (en Windows, `%APPDATA%\ipad-monitor\`) y no vuelve a pedirlo, aunque se reinicie. Cinco PIN incorrectos bloquean esa IP durante un minuto.

### USB

En Linux, el emisor habla con `usbmuxd`, que el sistema arranca al detectar el iPad. En Windows hace falta el servicio Apple Mobile Device, que instala iTunes. Al elegir **USB** en el panel, el emisor abre el enlace por cable y el visor cierra el Wi‑Fi. Si se desconecta el cable, el visor vuelve solo al Wi‑Fi.

## Pantalla extendida

**Linux.** Con gráficos Intel, el driver `intel` de Xorg crea una salida virtual `VIRTUAL1`. `install-linux.sh` ofrece configurarlo; a mano:

```bash
sudo install -m 644 scripts/linux/20-intel-virtual.conf /etc/X11/xorg.conf.d/
```

Después de cerrar sesión, `scripts/linux/ipad-extendido.sh on` la enciende a 1024×768 a la derecha (`on left` a la izquierda, `off` la apaga). El lanzador lo hace solo. Para deshacerlo, borrá el archivo de `/etc/X11/xorg.conf.d/` y cerrá sesión. La configuración solo cambia el driver de la placa Intel: una NVIDIA híbrida sigue disponible por PRIME offload. Sin Intel, un adaptador HDMI que simula un monitor cumple la misma función.

**Windows.** [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) agrega un monitor virtual. Configuralo en 1024×768 y extendé el escritorio con `Win + P`. Los scripts de `scripts/` (`list-monitors`, `set-resolution`, `restart-virtual-display`) ayudan a encontrarlo y ajustarlo.

## Controles del visor

En la pestaña derecha:

- **Touchpad.** Un dedo mueve el cursor: despacio va uno a uno para apuntar y rápido recorre más distancia. Un toque hace clic, un toque con dos dedos hace clic derecho y dos dedos desplazan. Para arrastrar, dejá el dedo quieto hasta que el fondo se ponga azul y después movelo.
- **Toque directo.** La imagen funciona como pantalla táctil: un toque hace clic en ese punto, mantener apretado hace clic derecho, un dedo arrastra y dos dedos desplazan.
- **Teclado.** Escribe en la ventana con foco en la PC. La fila superior tiene Esc, Tab, Win, Supr, flechas, Copiar, Pegar, Deshacer y Alt+Tab. **Ctrl** y **Alt** quedan armados para la tecla siguiente. En Linux, los caracteres que el teclado escribe con AltGr o con tilde también llegan.
- **Monitor.** Cambia la pantalla transmitida sin cortar la conexión.
- **Calidad.** Alterna entre nítida y fluida. La fluida usa menos red.

En el panel, **Status** muestra el enlace y la latencia de un mensaje de ida y vuelta. Si la imagen se corta, queda la última con el aviso **Reconectando…** durante 20 s.

## Compilar el visor

Ver [COMPILAR.md](COMPILAR.md). Se compila en Linux con Theos, en la misma PC o en un servidor.
