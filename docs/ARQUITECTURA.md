# Arquitectura del visor nativo

Cómo viajan la imagen y los controles entre la PC y el iPad. Para usarlo, ver [native/README.md](../native/README.md).

## Componentes

| Parte | Archivo | Función |
|---|---|---|
| Emisor | [server/ipadscreen_h264.py](../server/ipadscreen_h264.py) | Captura con FFmpeg, codifica H.264 y envía video, cursor y mensajes de control. |
| Enlace | [server/ipadscreen.py](../server/ipadscreen.py) | Emparejamiento con PIN, servidor Wi‑Fi y conexión USB por `usbmuxd` (Linux) o Apple Mobile Device (Windows). |
| Entrada | [server/ipadscreen_input_linux.py](../server/ipadscreen_input_linux.py), [server/ipadscreen_input.py](../server/ipadscreen_input.py) | Aplican puntero y teclado con XTest (Linux) o `SendInput` (Windows). |
| Visor | [native/ios/](../native/ios/) | Recibe el flujo ([StreamClient.m](../native/ios/StreamClient.m)), lo presenta con AVFoundation desde una cola propia ([IPSH264Renderer.m](../native/ios/IPSH264Renderer.m)) y envía los gestos ([IPSRemoteControls.m](../native/ios/IPSRemoteControls.m)). |

## Protocolo

Un único TCP. El emisor manda `IPSCRN03` y el tamaño del cuadro, y después paquetes con 4 bytes de longitud. Si el bit más alto de la longitud está encendido, el paquete es un mensaje de control en texto; si no, es un cuadro H.264 (AVCC, con SPS/PPS antes de cada cuadro clave). El visor responde con líneas de texto.

Por Wi‑Fi, el visor abre con `GET /raw?id=<dispositivo>&cn=<nonce>`. El emisor responde con `pin=<nonce>` (dispositivo nuevo) o `hello=<nonce>:<prueba>` (dispositivo conocido), y el visor contesta con una prueba HMAC‑SHA256 del PIN o de su clave. Al emparejarse con PIN, el emisor entrega `key=<clave>`, que ambos guardan.

| Del emisor al visor | Significado |
|---|---|
| `monitors=[…]` | Lista JSON de monitores. Habilita los controles en el panel. |
| `cursorimg=…`, `cursor=x,y` | Imagen del cursor y posición de 0 a 10000 sobre la imagen. `-1,-1` lo oculta. |
| `codec=h264` | Empieza un flujo H.264. El decodificador se reinicia. |
| `monitor=N`, `quality=sharp` o `smooth` | Monitor y calidad del flujo que empieza. |
| `mode=wifi` o `usb` | Modo de enlace compartido. Se informa al conectar y se confirma cuando el visor lo cambia. |
| `ping`, `rtt=N` | Latido cada 2 s y eco de la marca de tiempo que mandó el visor. |

| Del visor al emisor | Significado |
|---|---|
| `move=dx,dy` | Movimiento relativo en píxeles, hasta 400 por eje. |
| `at=x,y` | Posición absoluta de 0 a 10000 sobre la imagen. |
| `click=left`, `right` o `middle` | Clic completo. |
| `button=down` o `up` | Botón izquierdo sostenido, para arrastrar. El emisor lo suelta si el enlace se corta. |
| `scroll=N` | Pasos de rueda, de -12 a 12. |
| `key=nombre` | `enter`, `tab`, `escape`, `backspace`, `delete`, `space`, flechas, `home`, `end`, `pageup`, `pagedown`, `insert`, `win`, `f1` a `f12`. |
| `combo=ctrl+c` | Hasta tres modificadores (`ctrl`, `alt`, `shift`, `win`) y una tecla. |
| `text=base64` | Texto UTF‑8. |
| `monitor=N`, `quality=…`, `mode=…` | Cambian el flujo o el enlace sin cortar la conexión. |
| `refresh` | Pide un cuadro clave. El emisor reinicia el codificador, como máximo una vez por segundo. |
| `ping`, `rtt=N` | Latido y medición de latencia. |

Cada lado ignora los mensajes que no conoce, así que emisores y visores de distintas versiones se entienden sin las funciones nuevas.

## Codificación

FFmpeg captura a 24 FPS con `x11grab` (Linux) o `gdigrab` (Windows), sin el cursor: el cursor viaja aparte y el visor lo dibuja, así responde sin esperar al video. Codifica con `libx264`, preset `superfast`, `-tune zerolatency`, perfil Baseline 3.1 y sin cuadros B, y escribe FLV por la tubería: como FLV antepone el tamaño de cada cuadro, el emisor lo reenvía apenas termina.

| Enlace y calidad | Linux | Windows |
|---|---|---|
| Wi‑Fi nítida | `-crf 19 -maxrate 1500k -bufsize 500k` | `-crf 19 -maxrate 3M -bufsize 1200k` |
| Wi‑Fi fluida | `-crf 24 -maxrate 1000k -bufsize 350k` | `-crf 24 -maxrate 1800k -bufsize 900k` |
| USB | `-qp 20` (nítida) o `-qp 25` (fluida) | igual |
| Renovación de la imagen | refresco intra, una onda cada 96 cuadros | un cuadro clave cada 48 cuadros |

El refresco intra evita el cuadro clave completo, que pesaba unos 70 KB y frenaba el Wi‑Fi: el cuadro más grande baja a unos 6 KB. El tope de 1,5 Mbit/s en Linux se eligió porque el Wi‑Fi del iPad Mini 1 rinde entre 2 y 4 Mbit/s.

## Demora y cortes de red

- **Cola corta.** En Linux, el socket usa `SO_SNDBUF` de 24 KB y `TCP_NOTSENT_LOWAT` de 4 KB, para que el video no se acumule en las colas del Wi‑Fi. Sin ese tope se midieron 225 ms de ida y vuelta contra un mínimo de 4,6 ms.
- **Descarte de imagen atrasada.** El emisor compara la marca de tiempo de cada cuadro con el reloj. Si el atraso supera 1 s, descarta lo pendiente y reinicia el codificador, así el iPad salta a la imagen actual en lugar de reproducir lo atrasado.
- **Reconexión.** Si el visor se reconecta mientras el enlace anterior sigue abierto, el nuevo lo reemplaza. El visor conserva la última imagen con el aviso **Reconectando…** durante 20 s.
- **Cursor a 60 Hz.** El emisor sondea la posición del cursor 60 veces por segundo y la envía apenas cambia.
