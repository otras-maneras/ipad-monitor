#!/bin/sh
# Enciende o apaga la pantalla extendida del iPad (VIRTUAL1, 1024x768)
# a la derecha de la pantalla de la notebook.
#   scripts/linux/ipad-extendido.sh on|off [left|right]
set -e
OUTPUT=VIRTUAL1
MODE=1024x768_60
PRIMARY=$(xrandr | awk '/ connected primary/{print $1; exit}')
[ -n "$PRIMARY" ] || PRIMARY=$(xrandr | awk '/ connected/ && $1 != "'$OUTPUT'"{print $1; exit}')
if ! xrandr | grep -q "^$OUTPUT "; then
    echo "No existe $OUTPUT: falta instalar 20-intel-virtual.conf y cerrar sesión." >&2
    exit 1
fi
case "$1" in
on)
    SIDE=${2:-right}
    xrandr | grep -q "^  *$MODE " || \
        xrandr --newmode "$MODE" 63.50 1024 1072 1176 1328 768 771 775 798 -hsync +vsync
    xrandr --addmode "$OUTPUT" "$MODE" 2>/dev/null || true
    xrandr --output "$OUTPUT" --mode "$MODE" "--$SIDE-of" "$PRIMARY"
    xrandr --listactivemonitors
    ;;
off)
    xrandr --output "$OUTPUT" --off
    ;;
*)
    echo "Uso: $0 on|off [left|right]" >&2
    exit 2
    ;;
esac
