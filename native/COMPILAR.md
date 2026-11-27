# Compilar el visor en Linux

El visor (Objective‑C para iOS 9, ARMv7) se compila con Theos en cualquier Linux x86_64 o aarch64: la misma PC donde corre el emisor o un servidor. Las herramientas y el SDK se descargan dentro de la carpeta de trabajo; no hace falta `sudo` ni se cambia nada del sistema. Esta guía se probó en Xubuntu 26.04 (x86_64) y en un servidor Ubuntu.

Dependencias del sistema: `git curl make perl python3 rsync fakeroot dpkg-deb tar xz file`.

## 1. Carpeta de trabajo

**En la misma PC.** La carpeta de trabajo es `native/` del repositorio. Lo que se descarga (`theos/`, `bin/`, `tmp/`, `sdks-src/`) queda fuera de git.

```bash
cd native
```

**En un servidor.** Generá un ZIP con el contenido de `native/`, subilo y descomprimilo en una carpeta de trabajo (`servidor` es el alias SSH):

```bash
cd native && python3 -m zipfile -c ../ipad-monitor-fuentes.zip COMPILAR.md LICENSE README.md build ios && cd ..
ssh servidor 'mkdir -p ipad-monitor-build'
scp ipad-monitor-fuentes.zip servidor:ipad-monitor-build/
ssh servidor 'cd ipad-monitor-build && python3 -m zipfile -e ipad-monitor-fuentes.zip .'
```

## 2. Preparar las herramientas locales

Ejecutá el bloque desde la carpeta de trabajo. Comprueba primero las dependencias del sistema y se detiene si falta alguna. En ese caso, guardá la lista de faltantes para preparar una alternativa local o usar otro entorno. El instalador automático de Theos puede hacer cambios globales, así que esta guía usa descargas directas dentro de la carpeta de trabajo.

```bash
(
  set -eu
  test "$(id -u)" -ne 0 || { echo "Usá una cuenta sin privilegios de root"; exit 1; }
  test -f ios/Makefile || { echo "Entrá en la carpeta donde extrajiste el ZIP"; exit 1; }
  for cmd in git curl make perl python3 rsync fakeroot dpkg-deb tar xz file; do
    command -v "$cmd" >/dev/null || { echo "Falta: $cmd"; exit 1; }
  done
  arch=$(uname -m)
  case "$arch" in x86_64|aarch64) ;; *) echo "Arquitectura no prevista: $arch"; exit 1;; esac
  mkdir -p "$PWD/tmp"
  export TMPDIR="$PWD/tmp"
  export THEOS="$PWD/theos"

  if [ ! -f "$THEOS/makefiles/common.mk" ]; then
    git clone --depth 1 --recurse-submodules --shallow-submodules https://github.com/theos/theos.git "$THEOS"
  fi
  mkdir -p "$THEOS/toolchain" "$THEOS/sdks" "$PWD/bin"

  if [ ! -x "$THEOS/toolchain/linux/iphone/bin/clang" ]; then
    curl -fL "https://github.com/L1ghtmann/llvm-project/releases/download/test-210562a/iOSToolchain-${arch}.tar.xz" -o toolchain.tar.xz
    tar -xJf toolchain.tar.xz -C "$THEOS/toolchain"
  fi
  "$THEOS/toolchain/linux/iphone/bin/clang" --version

  if [ ! -d "$THEOS/sdks/iPhoneOS9.3.sdk" ]; then
    if [ ! -d sdks-src/.git ]; then
      git clone --depth 1 --filter=blob:none --sparse https://github.com/theos/sdks.git sdks-src
    fi
    git -C sdks-src sparse-checkout set iPhoneOS9.3.sdk
    cp -a sdks-src/iPhoneOS9.3.sdk "$THEOS/sdks/"
    # El SDK de Theos no enlaza con este toolchain sin estos arreglos.
    sh build/preparar-sdk.sh "$THEOS/sdks/iPhoneOS9.3.sdk"
  fi

  if [ ! -x "$THEOS/toolchain/linux/iphone/bin/ldid" ] && ! command -v ldid >/dev/null && [ ! -x "$PWD/bin/ldid" ]; then
    curl -fL "https://github.com/ProcursusTeam/ldid/releases/download/v2.1.5-procursus7/ldid_linux_${arch}" -o "$PWD/bin/ldid"
    chmod u+x "$PWD/bin/ldid"
  fi
)
```

Si `clang --version` falla por una biblioteca compartida faltante, guardá el error de `ldd theos/toolchain/linux/iphone/bin/clang`. La versión exacta de Ubuntu determina qué biblioteca necesita el toolchain.

### Arreglos del SDK

`build/preparar-sdk.sh` corrige la copia del SDK iPhoneOS9.3 de Theos. Su `libSystem.B.tbd` omite símbolos C y re-exporta `liblaunch`, que no existe; se reemplaza por el de [mstg/iOS-full-sdk](https://github.com/mstg/iOS-full-sdk), verificado por SHA256. `System.tbd` pierde la misma referencia a `liblaunch`, y todos los stubs dejan de declarar `i386` y `x86_64`, que hacían que el enlazador los tomara como simulador. Si el SDK ya estaba copiado de una compilación anterior sin arreglar, ejecutá el script a mano: `sh build/preparar-sdk.sh theos/sdks/iPhoneOS9.3.sdk`.

Versiones con las que se compiló la 0.3.0: Theos `8167f59de02fd32cf45b16bfcb1330dfa5c9974c`, SDK de Theos `0222fd5413cf4b9af096f37b4621afa2688572f7` y toolchain `test-210562a` (clang 11.1.0). El resultado del script sobre ese SDK coincide archivo por archivo con el usado para la 0.3.0. La compilación completa con estos scripts no se repitió.

## 3. Compilar y verificar

Desde la carpeta de trabajo:

```bash
sh build/compilar.sh
```

El script agrega `build/bin` al PATH. Ahí está `plistutil`, reemplazado por una versión en Python porque el del toolchain necesita una biblioteca `libplist` que no viene instalada.

Comprobá el paquete:

```bash
deb=$(ls ios/packages/*.deb | tail -1)
dpkg-deb -f "$deb" Package Version Architecture
verify=$(mktemp -d "$PWD/verify.XXXXXX")
dpkg-deb -x "$deb" "$verify"
file "$verify/Applications/IPadScreenH264.app/IPadScreenH264"
sha256sum "$deb"
```

El paquete debe mostrar `com.minipad.ipadscreenh264`, arquitectura `iphoneos-arm`, y el ejecutable debe ser Mach-O ARMv7 de 32 bits. Esto verifica la arquitectura. La compatibilidad en ejecución se comprueba en el iPad.

## 4. Instalarlo en el iPad

El paquete queda en `ios/packages/`. Si compilaste en un servidor, traelo con `scp servidor:ipad-monitor-build/ios/packages/*.deb .`. Pasalo al iPad e instalalo con Filza. Se instala como actualización de versiones anteriores, aunque se llamaran MiniPad o iPadScreen H264, porque el identificador `com.minipad.ipadscreenh264` no cambia.

La 0.3.0 compilada en Xubuntu con estos pasos dio un paquete idéntico al instalado salvo la firma del ejecutable (73 bytes dentro de `LC_CODE_SIGNATURE`).

[Theos para Linux](https://theos.dev/docs/installation-linux) · [SDK de Theos](https://github.com/theos/sdks) · [Toolchain Linux](https://github.com/L1ghtmann/llvm-project/releases/tag/test-210562a)
