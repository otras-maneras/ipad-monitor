#!/bin/sh
# Instalador de iPad Monitor para Linux (X11). Prepara el emisor H.264,
# crea el ícono "iPad Monitor" y, si se acepta, la pantalla extendida.
#   ./install-linux.sh
set -e
cd "$(dirname "$0")"
ROOT=$(pwd)

ask() {  # ask "pregunta" -> 0 si la respuesta es sí
    printf "%s [s/N] " "$1"
    read -r answer
    case "$answer" in [sSyY]*) return 0 ;; *) return 1 ;; esac
}

echo "== iPad Monitor para Linux =="

if [ "${XDG_SESSION_TYPE:-x11}" = "wayland" ]; then
    echo "Esta sesión usa Wayland. El emisor necesita una sesión X11 (por ejemplo XFCE)."
    echo "Podés instalar igual y usarlo al entrar con una sesión X11."
fi

# 1. Paquetes del sistema
missing=""
command -v ffmpeg >/dev/null 2>&1 || missing="$missing ffmpeg"
python3 -c "import venv, ensurepip" 2>/dev/null || missing="$missing python3-venv"
python3 -c "import ctypes.util, sys; sys.exit(not ctypes.util.find_library('Xtst'))" 2>/dev/null \
    || missing="$missing libxtst6"
if [ -n "$missing" ]; then
    echo "Faltan paquetes:$missing"
    if command -v apt-get >/dev/null 2>&1; then
        echo "Se instalan con apt (pide tu contraseña)."
        # shellcheck disable=SC2086
        sudo apt-get install -y $missing
    else
        echo "Instalalos con el gestor de paquetes de tu distribución y volvé a ejecutar este script."
        exit 1
    fi
fi
if ! ffmpeg -hide_banner -devices 2>/dev/null | grep -q x11grab; then
    echo "El FFmpeg instalado no trae x11grab. Instalá uno con soporte para X11."
    exit 1
fi

# 2. Entorno de Python
if [ ! -x .venv-linux/bin/python ]; then
    echo "Creando el entorno de Python en .venv-linux..."
    python3 -m venv .venv-linux
fi
.venv-linux/bin/python -m pip install -q -r requirements-linux.txt
chmod +x scripts/linux/*.sh

# 3. Ícono
if command -v xfce4-terminal >/dev/null 2>&1; then
    TERMINAL='xfce4-terminal --title "iPad Monitor" --geometry 52x24 --hide-menubar --hide-toolbar -x'
elif command -v gnome-terminal >/dev/null 2>&1; then
    TERMINAL='gnome-terminal --title "iPad Monitor" --'
elif command -v konsole >/dev/null 2>&1; then
    TERMINAL='konsole -e'
else
    TERMINAL='x-terminal-emulator -e'
fi
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
sed -e "s|@ROOT@|$ROOT|g" -e "s|@TERMINAL@|$TERMINAL|g" \
    scripts/linux/ipad-monitor.desktop.in > "$APPS/ipad-monitor.desktop"
chmod +x "$APPS/ipad-monitor.desktop"
DESKTOP_DIR=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ -d "$DESKTOP_DIR" ]; then
    cp "$APPS/ipad-monitor.desktop" "$DESKTOP_DIR/ipad-monitor.desktop"
    chmod +x "$DESKTOP_DIR/ipad-monitor.desktop"
    # XFCE pide confirmar los íconos nuevos; esto los marca como confiables.
    gio set "$DESKTOP_DIR/ipad-monitor.desktop" metadata::xfce-exe-checksum \
        "$(sha256sum "$DESKTOP_DIR/ipad-monitor.desktop" | cut -d' ' -f1)" 2>/dev/null || true
fi
echo "Ícono \"iPad Monitor\" creado en el menú${DESKTOP_DIR:+ y en el escritorio}."

# 4. Pantalla extendida (opcional, solo gráficos Intel con Xorg)
echo
if xrandr 2>/dev/null | grep -q "^VIRTUAL1 "; then
    echo "La pantalla extendida (VIRTUAL1) ya está disponible."
elif lspci 2>/dev/null | grep -Ei "vga|display" | grep -qi intel; then
    echo "Para usar el iPad como pantalla extendida, Xorg tiene que usar el driver"
    echo "intel con una salida virtual. Requiere tu contraseña y cerrar sesión."
    echo "Se deshace borrando /etc/X11/xorg.conf.d/20-intel-virtual.conf."
    if ask "¿Configurar la pantalla extendida?"; then
        if [ ! -e /usr/lib/xorg/modules/drivers/intel_drv.so ]; then
            sudo apt-get install -y xserver-xorg-video-intel
        fi
        sudo install -m 644 scripts/linux/20-intel-virtual.conf /etc/X11/xorg.conf.d/
        echo "Listo. Cerrá sesión y volvé a entrar para activarla."
        echo "Si el escritorio no aparece: Ctrl+Alt+F3, sudo rm /etc/X11/xorg.conf.d/20-intel-virtual.conf y reiniciar."
    fi
else
    echo "Sin gráficos Intel no se puede crear la pantalla virtual por software."
    echo "Un adaptador HDMI que simula un monitor sirve igual. Mientras tanto, iPad Monitor"
    echo "muestra la pantalla principal en espejo."
fi

# 5. Ahorro de energía del Wi-Fi (opcional)
if [ -d /etc/NetworkManager/conf.d ] && [ ! -e /etc/NetworkManager/conf.d/99-minipad-wifi-powersave-off.conf ]; then
    echo
    echo "El ahorro de energía del Wi-Fi provoca picos de demora en la imagen."
    if ask "¿Desactivarlo? (pide tu contraseña)"; then
        sudo install -m 644 scripts/linux/99-minipad-wifi-powersave-off.conf /etc/NetworkManager/conf.d/
        for dev in $(iw dev 2>/dev/null | awk '/Interface/{print $2}'); do
            sudo iw dev "$dev" set power_save off 2>/dev/null || true
        done
    fi
fi

echo
echo "Instalación terminada. Abrí \"iPad Monitor\" desde el escritorio o el menú."
