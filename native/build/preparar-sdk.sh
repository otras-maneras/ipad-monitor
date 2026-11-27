#!/bin/sh
# Corrige la copia del SDK iPhoneOS9.3 de theos/sdks para compilar el visor
# con el toolchain de Linux. Reproduce los arreglos de la compilación de la 0.3.0:
#  1. libSystem.B.tbd del SDK de Theos omite símbolos C y re-exporta liblaunch,
#     que no existe: se reemplaza por el del SDK público de mstg/iOS-full-sdk.
#  2. System.tbd también re-exporta liblaunch: se quita esa entrada.
#  3. Los stubs declaran i386 y x86_64 en su lista principal de arquitecturas y
#     el enlazador los toma como simulador: se dejan armv7, armv7s y arm64.
# Uso: native/build/preparar-sdk.sh "$THEOS/sdks/iPhoneOS9.3.sdk"
set -eu
SDK=${1:?Indicá la carpeta iPhoneOS9.3.sdk}
test -f "$SDK/usr/lib/libSystem.B.tbd" || { echo "No parece un SDK de iOS: $SDK" >&2; exit 1; }
URL=https://raw.githubusercontent.com/mstg/iOS-full-sdk/master/iPhoneOS9.3.sdk/usr/lib/libSystem.tbd
SUM=ceb0f748e1ebda73887f66ce77bb8ce8b13fe00b02aba2937f859a6b33f781d3

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -fsSL "$URL" -o "$tmp"
echo "$SUM  $tmp" | sha256sum -c --quiet - || { echo "libSystem.tbd descargado no coincide" >&2; exit 1; }
cp "$tmp" "$SDK/usr/lib/libSystem.B.tbd"
chmod 644 "$SDK/usr/lib/libSystem.B.tbd"

sed -i 's|/usr/lib/system/liblaunch.dylib, ||' "$SDK/System/Library/Frameworks/System.framework/System.tbd"

# Solo archivos regulares: los enlaces simbólicos apuntan a libSystem.B.tbd.
find "$SDK" -name '*.tbd' -type f -exec sed -i -E \
    '0,/^archs:/ s/^(archs: *\[ *armv7, armv7s, arm64), i386, x86_64 \]/\1 ]/' {} +
echo "SDK corregido: $SDK"
