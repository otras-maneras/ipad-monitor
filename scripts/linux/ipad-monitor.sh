#!/bin/sh
# iPad Monitor: enciende la pantalla del iPad, arranca el emisor H.264 por Wi-Fi
# y muestra la IP y el PIN. Al cerrar la ventana se apaga la pantalla extra.
cd "$(dirname "$0")/../.." || exit 1
ROOT=$(pwd)

pause_and_exit() {
    echo
    printf "Presioná Enter para cerrar esta ventana. "
    read -r _
    exit "${1:-1}"
}

if [ ! -x .venv-linux/bin/python ] || ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Faltan dependencias. Ver native/README.md, sección Emisor Linux."
    pause_and_exit 1
fi

# IP de la interfaz por la que sale el tráfico (normalmente el Wi-Fi).
IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')
if [ -z "$IP" ]; then
    echo "No hay conexión de red. Conectá la PC al Wi-Fi y volvé a abrir iPad Monitor."
    pause_and_exit 1
fi

EXTENDED=0
if xrandr | grep -q "^VIRTUAL1 "; then
    if "$ROOT/scripts/linux/ipad-extendido.sh" on >/dev/null 2>&1; then
        EXTENDED=1
        sleep 1
    fi
fi

# Pantalla de 1024x768 si está la extendida; si no, la principal en espejo.
MONITOR=$(.venv-linux/bin/python -B -c '
from server.screen_capture import list_monitors
monitors = [m for m in list_monitors() if m["id"] > 0]
ipad = [m["id"] for m in monitors if (m["width"], m["height"]) == (1024, 768) and m["left"] > 0]
print(ipad[-1] if ipad else monitors[0]["id"])
' 2>/dev/null)
[ -n "$MONITOR" ] || MONITOR=1

cleanup() {
    if [ "$EXTENDED" = 1 ]; then
        "$ROOT/scripts/linux/ipad-extendido.sh" off >/dev/null 2>&1
    fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP

clear
echo "=============================================="
echo "  iPad Monitor · pantalla para el iPad"
echo "=============================================="
if [ "$EXTENDED" = 1 ]; then
    echo "  Modo:  pantalla extendida a la derecha"
else
    echo "  Modo:  espejo de la pantalla principal"
fi
echo "  En el iPad: Wi-Fi → Mac → Address"
echo "  Para USB: conectá el cable y elegí USB"
echo "  en el panel del visor."
echo "  IP:    $IP"
echo "  El PIN aparece abajo. Un iPad ya emparejado"
echo "  entra sin PIN."
echo "  Para terminar, cerrá esta ventana."
echo "=============================================="
echo

# Copia de la salida para diagnosticar después.
LOG_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ipad-monitor"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/emisor.log"
date "+--- %Y-%m-%d %H:%M:%S ---" >> "$LOG"
STATUS_FILE="$LOG_DIR/.estado"
{ .venv-linux/bin/python -B -m server.ipadscreen_h264 --bind "$IP" --usb --monitor "$MONITOR" 2>&1
  echo $? > "$STATUS_FILE"; } | tee -a "$LOG"
STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo 1)
[ "$STATUS" = 0 ] || pause_and_exit "$STATUS"
