#!/bin/sh
# Compila el visor desde la carpeta de trabajo de la guía de compilación
# (la que tiene ios/, build/, theos/ y bin/).
# Uso: sh build/compilar.sh   (con una cuenta sin privilegios de root)
set -eu
cd "$(dirname "$0")/.."
test "$(id -u)" -ne 0 || { echo "Ejecutar con una cuenta sin privilegios de root" >&2; exit 1; }
export THEOS="$PWD/theos"
export TMPDIR="$PWD/tmp"
mkdir -p "$TMPDIR"
# build/bin trae plistutil con plistlib de Python: el del toolchain necesita una
# libplist compartida que no está instalada.
export PATH="$PWD/build/bin:$PWD/bin:$THEOS/toolchain/linux/iphone/bin:$PATH"
make -C ios clean
make -C ios -j2 package FINALPACKAGE=1
ls -lh ios/packages/*.deb
