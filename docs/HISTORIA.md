# Historia y mediciones

Cómo llegó iPad Monitor a su forma actual y qué se midió en el camino. Sirve para entender por qué el código hace lo que hace.

## Del modo web al visor nativo

1. **Modo web (Windows).** Servidor FastAPI, captura con MSS y Pillow, y Safari de iOS 9 como cliente. MJPEG dejaba la pantalla negra en iOS 9, así que el espejo pasó a polling de JPEG. Se sumaron touchpad, teclado, estadísticas, biblioteca y cine. La demora quedó en 100–300 ms: útil para control, no como monitor.
2. **iPadScreen original.** Se probó el visor nativo [iPadScreen 1.0.2](https://github.com/demirfirat/ipadScreen/tree/v1.0.2) con un emisor JPEG adaptado de macOS a Windows. Por USB, 1024×768 con JPEG de calidad 75 daba 10–20 FPS; por Wi‑Fi era lento incluso a 800×600.
3. **H.264.** FFmpeg a 1024×768 y 24 FPS con un visor propio (iPadScreen H264, hoy iPad Monitor) que presenta con AVFoundation. Por Wi‑Fi fue mucho más rápido que VLC.
4. **Controles (0.2.0) y rendimiento (0.3.0).** La 0.2.0 sumó USB, touchpad, teclado y selector de monitor. Una revisión del código encontró las causas de los cortes y la nitidez variable de la 0.2.0, y la 0.3.0 las corrigió:

| Síntoma | Causa | Cambio |
|---|---|---|
| Corte a negro por Wi‑Fi | El visor ocultaba el video al caerse la conexión | Última imagen con aviso de reconexión durante 20 s |
| Congelamientos al abrir menús | El video pasaba por el hilo de la interfaz | Cola propia para AVFoundation y pedido de cuadro clave con `refresh` |
| Nitidez que oscilaba | Un cuadro clave cada 0,5 s con tope de 3 Mbit/s | Cuadro clave cada 2 s y preset `superfast` |
| Controles mudos | El fail‑safe de PyAutoGUI descartaba comandos en las esquinas | `SendInput` directo |
| Un cuadro de demora fija | El emisor esperaba el cuadro siguiente para cortar el actual | Salida FLV, que antepone el tamaño |

Con un desplazamiento sintético a 1024×768, la 0.3.0 bajó el tráfico de 3,0 a 1,7 Mbit/s en movimiento y de 2,1 a 0,3 Mbit/s con la pantalla quieta.

## Linux

5. **Emisor Linux.** El mismo emisor con `x11grab` en X11, controles con XTest (sin permisos de administrador) y USB con `usbmuxd`. La app del iPad no cambió.
6. **Pantalla extendida.** En Xorg, una región RandR agregada con `--setmonitor` no deja entrar al cursor, y una salida HDMI sin monitor no enciende. El driver `intel` con `VirtualHeads` crea `VIRTUAL1`, que se comporta como un monitor real. Con DRI2 el driver pedía `i965`, que Mesa ya no trae, y OpenGL caía a render por software; `Option "DRI" "3"` lo resolvió.
7. **Demora en Wi‑Fi.** Con el iPad Mini 1 en 5 GHz:
   - El ahorro de energía del Wi‑Fi de la PC causaba picos: el promedio de ping al iPad bajó de 56 a 26 ms al desactivarlo.
   - TCP llenaba las colas del Wi‑Fi: 225 ms de ida y vuelta contra un mínimo de 4,6 ms. Con `SO_SNDBUF` de 24 KB quedó entre 10 y 30 ms.
   - Tras un corte de 1,5 s, el iPad reproducía unos 39 cuadros viejos. Descartar la imagen atrasada y reiniciar el codificador lo bajó a unos 10. Con un umbral de 350 ms los reinicios eran tan seguidos que causaban tirones; quedó en 1 s.
   - El cuadro clave de unos 72 KB frenaba también al cursor. El refresco intra lo bajó a unos 6 KB y además redujo el tráfico (0,43 → 0,36 Mbit/s con pantalla quieta).
   - Con una ventana en movimiento, un tope de 1,5 Mbit/s en lugar de 3 redujo el tráfico un 30 % y los picos un 34 %, con SSIM 0,979 contra 0,980.
8. **Compilación en Linux.** El visor se compila con Theos en la misma PC. El SDK iPhoneOS 9.3 de Theos necesita tres arreglos (`native/build/preparar-sdk.sh`). La 0.3.0 compilada así coincide con la compilada antes en un servidor, salvo la firma del ejecutable.
9. **iPad Monitor 0.3.1.** El proyecto, antes MiniPad, cambió de nombre. El modo web sumó PIN y soporte para Linux.

## Sin probar

- La 0.3.1 en el iPad (es la 0.3.0 con otro nombre).
- Los instaladores y el modo web en Windows después de los cambios de Linux.
- Perfil H.264 High y captura con `ddagrab` en Windows.
