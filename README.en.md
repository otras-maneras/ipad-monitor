# iPad Monitor

[Español](README.md) · **English**

Use an **iPad Mini 1** (iOS 9.3.5, 32‑bit) as an **extended display** for your PC, with touchpad and keyboard, over **Wi‑Fi or USB**. Works with **Linux (X11)** and **Windows 10/11**.

There are two modes:

- **Native viewer** (recommended): an app for jailbroken iPads that receives low‑latency H.264 video, like one more monitor.
- **Web mode**: mirror, touchpad, keyboard, library and cinema from Safari, no jailbreak needed. Simpler, with more latency.

> The rest of the documentation, the installers and the PC‑side messages are in Spanish.

## Requirements

- An iPad Mini 1 (or another 32‑bit iPad on iOS 9) with a jailbreak and Filza, for the native viewer. See [docs/IPAD.md](docs/IPAD.md).
- The PC and the iPad on the same Wi‑Fi network (5 GHz works best), or a USB data cable.

## 1. Install the app on the iPad

Download `ipad-monitor-0.3.1.deb` from [Releases](https://github.com/otras-maneras/ipad-monitor/releases), copy it to the iPad and install it with Filza. It shows up as **iPad Monitor**. You can also build it yourself: [native/COMPILAR.md](native/COMPILAR.md).

## 2. Install on the PC

### Linux

Tested on Xubuntu 26.04 with XFCE on X11. Wayland is not supported.

```bash
git clone https://github.com/otras-maneras/ipad-monitor.git
cd ipad-monitor
./install-linux.sh
```

The installer adds FFmpeg and Python if they are missing, creates an **iPad Monitor** icon on the desktop and in the menu, and offers two optional tweaks that ask for your password:

- **Extended display** at 1024×768, to the right of the main screen. It uses a virtual output of Xorg's `intel` driver, so it only works with Intel graphics and needs one logout. Without Intel graphics, an HDMI dummy plug does the same job; until then, the iPad mirrors the main screen.
- **Wi‑Fi power saving off**, which avoids latency spikes.

### Windows

Download the repository (**Code → Download ZIP**) and double‑click **`install-windows.bat`**. It installs Python and FFmpeg with `winget` if they are missing (asking first), creates an **iPad Monitor** shortcut and offers to install [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) for the extended display. Set the virtual monitor to 1024×768 and extend the desktop with `Win + P`. USB needs iTunes or the Apple Mobile Device service.

> The Windows installer has not been tested on Windows yet. If it fails, the sender can be started by hand as shown below.

## 3. Connect

1. Double‑click **iPad Monitor** on the PC. The window shows the IP address and a PIN.
2. On the iPad, open **iPad Monitor**, choose **Wi‑Fi → Mac → Address**, type the IP and then the PIN. Next time it connects without a PIN.
3. To use the cable, plug it in and choose **USB** in the viewer's panel.

Closing the window on the PC stops everything.

### Starting the sender by hand

```bash
# Linux
.venv-linux/bin/python -B -m server.ipadscreen_h264 --bind PC_IP --usb --monitor 2
```

```powershell
# Windows
.\.venv\Scripts\python.exe -B -m server.ipadscreen_h264 --bind PC_IP --usb --monitor 2
```

`--monitor` picks the screen to send (a 1024×768 one is shown unscaled). `--calidad fluida` starts with stronger compression; the viewer can switch quality from its panel. More options in [native/README.md](native/README.md).

## Viewer controls

- **Touchpad:** one finger moves the pointer, a tap clicks, a two‑finger tap right‑clicks, two fingers scroll. Rest a finger until the background turns blue to drag.
- **Direct touch:** the picture works as a touchscreen.
- **Keyboard:** types into the focused window on the PC, with Esc, Tab, arrows, copy, paste, undo and Alt+Tab.
- **Monitor** and **quality** switch without dropping the connection. **Status** shows the round‑trip latency.

## Web mode

```bash
.venv-linux/bin/python run.py      # Linux
```

On Windows, double‑click `run.bat`. In Safari on the iPad, open `http://PC_IP:8765/` and enter the PIN shown in the console. Each browser asks for it only once. Details (in Spanish): [docs/WEB.md](docs/WEB.md).

## How it works

The sender captures the screen with FFmpeg (`x11grab` or `gdigrab`) at 24 FPS and encodes H.264 Baseline with `zerolatency`. The pointer travels separately so it responds without waiting for the video. To keep Wi‑Fi latency low on Linux, it uses intra refresh instead of full keyframes, caps the bitrate at 1.5 Mbit/s, keeps the socket queue short and drops stale frames after a network stall. The protocol and the measurements behind these choices are in [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) and [docs/HISTORIA.md](docs/HISTORIA.md) (in Spanish).

## Limitations

- Over Wi‑Fi, small hiccups remain when the iPad's signal drops; over USB they don't.
- The resolution is 1024×768, the iPad Mini 1's native one. Good for text, chat, references and control; not for games or fast video.
- Traffic is unencrypted on the local network. Both the viewer and web mode require a PIN, but use them only on trusted networks.

## License

MIT, see [LICENSE](LICENSE). The viewer in `native/` is derived from [iPadScreen v1.0.2](https://github.com/demirfirat/ipadScreen/tree/v1.0.2) and keeps its MIT license in [native/LICENSE](native/LICENSE).
