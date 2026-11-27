# iPad Monitor

**Español** · [English](README.en.md)

Usá un **iPad Mini 1** (iOS 9.3.5, 32 bits) como **pantalla extendida** de la PC, con touchpad y teclado, por **Wi‑Fi o USB**. Funciona con **Linux (X11)** y **Windows 10/11**.

Tiene dos modos:

- **Visor nativo** (recomendado): una app para iPad con jailbreak que recibe video H.264 con poca demora, como un monitor más.
- **Modo web**: espejo, touchpad, teclado, biblioteca y cine desde Safari, sin jailbreak. Más simple, con más demora.

## Qué hace falta

- Un iPad Mini 1 (u otro iPad de 32 bits con iOS 9) con jailbreak y Filza, para el visor nativo. Ver [docs/IPAD.md](docs/IPAD.md).
- La PC y el iPad en la misma red Wi‑Fi (mejor de 5 GHz), o un cable USB de datos.

## 1. Instalar la app en el iPad

Descargá `ipad-monitor-0.3.1.deb` desde [Releases](https://github.com/otras-maneras/ipad-monitor/releases), pasalo al iPad e instalalo con Filza. Aparece como **iPad Monitor**. También podés compilarla: [native/COMPILAR.md](native/COMPILAR.md).

## 2. Instalar en la PC

### Linux

Probado en Xubuntu 26.04 con XFCE sobre X11. Wayland no está soportado.

```bash
git clone https://github.com/otras-maneras/ipad-monitor.git
cd ipad-monitor
./install-linux.sh
```

El instalador agrega FFmpeg y Python si faltan, crea el ícono **iPad Monitor** en el escritorio y en el menú, y ofrece dos ajustes opcionales que piden tu contraseña:

- **Pantalla extendida** de 1024×768 a la derecha de la principal. Usa una salida virtual del driver `intel` de Xorg, así que solo sirve con gráficos Intel y hay que cerrar sesión una vez. Sin Intel, un adaptador HDMI que simula un monitor da el mismo resultado; mientras tanto, el iPad muestra la pantalla principal en espejo.
- **Wi‑Fi sin ahorro de energía**, que evita picos de demora.

### Windows

Descargá el repositorio (**Code → Download ZIP**) y hacé doble clic en **`install-windows.bat`**. Instala Python y FFmpeg con `winget` si faltan (preguntando antes), crea el acceso directo **iPad Monitor** y ofrece instalar [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) para la pantalla extendida. Configurá el monitor virtual en 1024×768 y extendé el escritorio con `Win + P`. Para USB hace falta iTunes o el servicio Apple Mobile Device.

> El instalador de Windows todavía no se probó en Windows. Si falla, el emisor se arranca a mano como explica [native/README.md](native/README.md).

## 3. Conectar

1. Doble clic en **iPad Monitor** en la PC. La ventana muestra la IP y un PIN.
2. En el iPad, abrí **iPad Monitor**, elegí **Wi‑Fi → Mac → Address**, escribí la IP y después el PIN. La próxima vez entra sin PIN.
3. Para usar el cable, conectalo y elegí **USB** en el panel del visor.

Cerrar la ventana de la PC detiene todo. Controles del visor y opciones del emisor: [native/README.md](native/README.md).

## Modo web

```bash
.venv-linux/bin/python run.py      # Linux
```

En Windows, doble clic en `run.bat`. En Safari del iPad abrí `http://IP_DE_LA_PC:8765/` e ingresá el PIN que muestra la consola. Detalles: [docs/WEB.md](docs/WEB.md).

## Documentación

| Archivo | Contenido |
|---|---|
| [native/README.md](native/README.md) | Visor y emisor: uso, opciones, pantalla extendida y controles |
| [docs/IPAD.md](docs/IPAD.md) | Preparar el iPad e instalar la app |
| [docs/WEB.md](docs/WEB.md) | Modo web: páginas, PIN y API |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Protocolo, codificación y manejo de la demora |
| [native/COMPILAR.md](native/COMPILAR.md) | Compilar la app con Theos en Linux |
| [docs/HISTORIA.md](docs/HISTORIA.md) | Cómo se llegó hasta acá y qué se midió |

## Limitaciones

- Por Wi‑Fi quedan tirones leves cuando la señal del iPad tiene cortes; por USB no.
- La resolución es 1024×768, la del iPad Mini 1. Juegos y video rápido no son la idea; texto, chat, referencias y control sí.
- El tráfico va sin cifrar dentro de la red local. El visor y el modo web piden PIN, pero conviene usarlos solo en redes de confianza.

## Licencia

MIT, ver [LICENSE](LICENSE). El visor en `native/` deriva de [iPadScreen v1.0.2](https://github.com/demirfirat/ipadScreen/tree/v1.0.2) y conserva su licencia MIT en [native/LICENSE](native/LICENSE).
