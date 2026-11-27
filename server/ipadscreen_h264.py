"""Emisor H.264 y controles de iPad Monitor por Wi-Fi o USB."""

import argparse
import asyncio
import base64
import ctypes
import io
import json
import os
import re
import shutil
import socket
import struct
import sys
from ctypes import wintypes

from PIL import Image, ImageDraw

from server.ipadscreen import packet, serve, serve_usb
from server.screen_capture import list_monitors


SIZE = (1024, 768)
FPS = 24
# Un cuadro clave cada 2 s. El visor pide uno antes con "refresh" si lo necesita.
KEYFRAME_INTERVAL = 48
# Con refresco intra no hay cuadros clave periódicos: cada cuadro renueva una
# franja y la imagen entera se renueva cada 4 s. El pico de unos 70 KB cada 2 s
# baja a unos 6 KB y el tráfico total también baja, así el Wi-Fi no se frena y
# el cursor no salta. Un visor que pierde un cuadro sigue pidiendo "refresh".
INTRA_REFRESH_INTERVAL = 96
USB_PORT = 8769
# Atraso tolerado antes de descartar lo pendiente y empezar con un cuadro clave
# nuevo (unos 200 ms de reinicio). Por debajo, el visor se pone al día solo: el
# búfer de envío es chico, así que se recupera rápido. Con 0,35 s el iPad real
# reiniciaba cada pocos segundos y cada cuadro clave nuevo traía otro tirón.
MAX_LAG = 1.0
# Bytes de video que el sistema puede tener encolados sin enviar.
UNSENT_LIMIT = 4 * 1024
# Tope del búfer de envío del socket, que incluye lo enviado sin confirmar. Sin
# tope, TCP llena las colas del Wi-Fi y la imagen llega con 200 ms o más de
# demora; con 24 KB alcanza para unos 6 Mbit/s con 30 ms de ida y vuelta.
SEND_BUFFER = 24 * 1024
# Sondeo del cursor: 60 Hz, como la pantalla del iPad.
CURSOR_INTERVAL = 1 / 60
QUALITIES = ("sharp", "smooth")
PRESETS = ("ultrafast", "superfast", "veryfast", "faster")
LINUX = sys.platform.startswith("linux")


def input_module():
    """Módulo de entrada de la plataforma: SendInput en Windows, XTest en Linux/X11."""
    if LINUX:
        from server import ipadscreen_input_linux as module
    else:
        from server import ipadscreen_input as module
    return module


def cursor_position():
    if LINUX:
        return input_module().cursor_position()
    point = wintypes.POINT()
    visible = ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return visible, point.x, point.y


async def drain_stream(writer):
    # asyncio.timeout y no wait_for: en Python 3.11 wait_for puede tragarse la
    # cancelación y dejar colgado el cambio de monitor o de calidad.
    try:
        async with asyncio.timeout(4):
            await writer.drain()
    except TimeoutError as error:
        raise OSError("El enlace dejó de aceptar datos durante 4 s") from error


def parameter_sets(record):
    """SPS y PPS de un AVCDecoderConfigurationRecord, como NAL con longitud."""
    output = bytearray()
    offset = 5
    for mask in (0x1F, 0xFF):
        count = record[offset] & mask
        offset += 1
        for _ in range(count):
            size = int.from_bytes(record[offset:offset + 2], "big")
            output += struct.pack("!I", size) + record[offset + 2:offset + 2 + size]
            offset += 2 + size
    return bytes(output)


async def access_units(reader):
    """Entrega (marca de tiempo en s, cuadro AVCC) apenas FFmpeg lo escribe.

    FLV antepone el tamaño de cada cuadro, así que no hace falta esperar el
    comienzo del siguiente para saber dónde termina el actual.
    """
    try:
        if (await reader.readexactly(13))[:3] != b"FLV":
            raise ValueError("FFmpeg no entregó FLV")
        headers = b""
        while True:
            tag = await reader.readexactly(11)
            size = int.from_bytes(tag[1:4], "big")
            stamp = int.from_bytes(tag[7:8] + tag[4:7], "big") / 1000
            body = (await reader.readexactly(size + 4))[:size]
            if tag[0] != 9 or size < 5 or body[0] & 15 != 7:
                continue
            if body[1] == 0:
                headers = parameter_sets(body[5:])
                continue
            if body[1] != 1:
                continue
            payload = bytearray()
            types = set()
            offset = 5
            while offset + 4 <= size:
                length = int.from_bytes(body[offset:offset + 4], "big")
                nal = body[offset + 4:offset + 4 + length]
                offset += 4 + length
                if not nal or len(nal) != length:
                    raise ValueError("Cuadro H.264 incompleto")
                kind = nal[0] & 31
                if kind in (6, 9):
                    continue
                types.add(kind)
                payload += struct.pack("!I", length) + nal
            if 5 in types and 7 not in types:
                payload[:0] = headers
            if payload:
                yield stamp, bytes(payload)
    except asyncio.IncompleteReadError:
        return


def cursor_image():
    image = Image.new("RGBA", (17, 26))
    ImageDraw.Draw(image).polygon(
        [(0, 0), (0, 20), (5, 15), (12, 24), (15, 21), (8, 12), (15, 9)],
        fill="white", outline="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return b"cursorimg=0,0,17,26," + base64.b64encode(buffer.getvalue())


def picture_size(monitor):
    width, height = monitor["width"], monitor["height"]
    scale = min(SIZE[0] / width, SIZE[1] / height)
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


async def send_cursor(writer, monitor, moved):
    previous = None
    clock = asyncio.get_running_loop().time
    next_ping = clock() + 2
    width, height = monitor["width"], monitor["height"]
    picture_width, picture_height = picture_size(monitor)
    while True:
        visible, x, y = cursor_position()
        x -= monitor["left"]
        y -= monitor["top"]
        position = (-1, -1)
        if visible and 0 <= x < width and 0 <= y < height:
            output_x = (SIZE[0] - picture_width) / 2 + x * picture_width / width
            output_y = (SIZE[1] - picture_height) / 2 + y * picture_height / height
            position = (int(output_x * 10000 / SIZE[0]), int(output_y * 10000 / SIZE[1]))
        sent = False
        if position != previous:
            writer.write(packet(f"cursor={position[0]},{position[1]}".encode(), control=True))
            previous = position
            sent = True
        if clock() >= next_ping:
            writer.write(packet(b"ping", control=True))
            next_ping = clock() + 2
            sent = True
        if sent:
            await drain_stream(writer)
        # Un movimiento hecho desde el iPad se informa enseguida, sin esperar el sondeo.
        try:
            async with asyncio.timeout(CURSOR_INTERVAL):
                await moved.wait()
        except TimeoutError:
            pass
        moved.clear()


def limit_send_queue(writer):
    """Deja poco video sin enviar en el sistema: si la red se traba, el atraso se
    acumula en el emisor, donde se puede descartar, y no en el socket."""
    sock = writer.get_extra_info("socket")
    if sock is None or sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    if LINUX:  # En Windows no se probó; allí el emisor ya andaba bien.
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFFER)
        except OSError:
            pass
    option = getattr(socket, "TCP_NOTSENT_LOWAT", 25 if LINUX else None)
    if option is not None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, option, UNSENT_LIMIT)
        except OSError:
            pass


async def send_video(writer, command):
    """Envía el video. Devuelve True si quedó atrasado y conviene reiniciar el codificador."""
    limit_send_queue(writer)
    encoder = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE)
    clock = asyncio.get_running_loop().time
    offset = None
    try:
        async for stamp, unit in access_units(encoder.stdout):
            # Cuánto tarda un cuadro desde la captura hasta salir. El menor valor
            # visto es el normal; lo que lo supere es atraso por la red.
            delay = clock() - stamp
            offset = delay if offset is None else min(offset, delay)
            if delay - offset > MAX_LAG:
                print(f"Imagen atrasada {int((delay - offset) * 1000)} ms: "
                      "se descarta y se envía una nueva", flush=True)
                return True
            writer.write(packet(unit))
            await drain_stream(writer)
        raise OSError("FFmpeg dejó de enviar H.264")
    finally:
        if encoder.returncode is None:
            try:
                encoder.terminate()
            except ProcessLookupError:
                pass
        # Drain the pipe so the subprocess transport can finish closing.
        await encoder.communicate()


def rate_control(usb, quality):
    if usb:
        return ["-qp", "20" if quality == "sharp" else "25"]
    if LINUX:
        # El Wi-Fi del iPad Mini rinde unos 2-4 Mbit/s y se encola al mover
        # ventanas. Con una ventana en movimiento, 1,5 Mbit/s bajó el tráfico un
        # 30 % y los picos un 34 % frente a 3 Mbit/s, con SSIM 0,979 contra 0,980.
        if quality == "sharp":
            return ["-crf", "19", "-maxrate", "1500k", "-bufsize", "500k"]
        return ["-crf", "24", "-maxrate", "1000k", "-bufsize", "350k"]
    if quality == "sharp":
        return ["-crf", "19", "-maxrate", "3M", "-bufsize", "1200k"]
    return ["-crf", "24", "-maxrate", "1800k", "-bufsize", "900k"]


def encoder_command(monitor, usb=False, quality="sharp", preset="superfast", intra=False):
    width, height = picture_size(monitor)
    fit = []
    if (monitor["width"], monitor["height"]) != SIZE:
        fit = ["-vf", f"scale={width}:{height},pad=1024:768:(ow-iw)/2:(oh-ih)/2"]
    x264 = "scenecut=0"
    if intra:
        x264 += ":intra-refresh=1"
    if usb:
        x264 += ":ipratio=1.0"
    size = f'{monitor["width"]}x{monitor["height"]}'
    if LINUX:
        source = f'{os.environ["DISPLAY"]}+{monitor["left"]},{monitor["top"]}'
        capture = ["-f", "x11grab", "-framerate", str(FPS), "-draw_mouse", "0",
                   "-video_size", size, "-i", source]
    else:
        capture = ["-f", "gdigrab", "-framerate", str(FPS), "-draw_mouse", "0",
                   "-offset_x", str(monitor["left"]), "-offset_y", str(monitor["top"]),
                   "-video_size", size, "-i", "desktop"]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        *capture,
        *fit,
        "-an", "-c:v", "libx264", "-preset", preset, "-tune", "zerolatency",
        "-pix_fmt", "yuv420p", "-profile:v", "baseline", "-level:v", "3.1",
        "-g", str(INTRA_REFRESH_INTERVAL if intra else KEYFRAME_INTERVAL), "-bf", "0", *rate_control(usb, quality),
        "-x264-params", x264,
        "-flush_packets", "1", "-flvflags", "no_duration_filesize", "-f", "flv", "pipe:1",
    ]


async def read_controls(reader, writer, monitors, selected, quality, moved, held, refreshed, link):
    """Aplica los comandos del visor. Devuelve (monitor, calidad) para reiniciar el video."""
    # El módulo de entrada usa píxeles físicos: MSS ya activó el modo DPI al
    # enumerar los monitores, así captura y cursor coinciden.
    apply_input = input_module().apply_input

    clock = asyncio.get_running_loop().time
    monitor = monitors[selected]
    while True:
        try:
            async with asyncio.timeout(12):
                line = await reader.readline()
        except TimeoutError as error:
            raise OSError("El visor dejó de responder a los latidos durante 12 s") from error
        if not line:
            return None
        line = line.strip()
        if match := re.fullmatch(rb"monitor=(\d{1,3})", line):
            target = int(match[1])
            if target in monitors and target != selected:
                return target, quality
        elif match := re.fullmatch(rb"quality=([a-z]{1,12})", line):
            target = match[1].decode()
            if target in QUALITIES and target != quality:
                return selected, target
        elif line == b"refresh":
            # El visor perdió un cuadro: reiniciar FFmpeg le da un cuadro clave
            # en unos 200 ms. El margen evita reinicios en cadena.
            if clock() - refreshed[0] > 1:
                refreshed[0] = clock()
                return selected, quality
        elif match := re.fullmatch(rb"mode=(wifi|usb)", line):
            # Modo de enlace elegido en el visor: se guarda, se confirma por este
            # enlace y, si vuelve a Wi-Fi, se cierra el USB.
            mode = match[1].decode()
            if link["mode"] != mode:
                link["mode"] = mode
                print(f"Modo {'USB' if mode == 'usb' else 'Wi-Fi'} elegido en el iPad", flush=True)
            writer.write(packet(line, control=True))
            usb = link.get("usb")
            if mode == "wifi" and usb is not None and not usb.done():
                await drain_stream(writer)
                usb.cancel()
        elif re.fullmatch(rb"rtt=\d{1,20}", line):
            writer.write(packet(line, control=True))
        elif apply_input(line, monitor, held):
            moved.set()


async def stream_monitor(reader, writer, monitors, selected, usb, quality, preset, intra, held, refreshed, link):
    monitor = monitors[selected]
    writer.write(packet(b"codec=h264", control=True))
    writer.write(packet(f"monitor={selected}".encode(), control=True))
    writer.write(packet(f"quality={quality}".encode(), control=True))
    moved = asyncio.Event()
    control = asyncio.create_task(
        read_controls(reader, writer, monitors, selected, quality, moved, held, refreshed, link))
    tasks = {control, asyncio.create_task(send_cursor(writer, monitor, moved))}
    video = asyncio.create_task(send_video(writer, encoder_command(monitor, usb, quality, preset, intra)))
    tasks.add(video)
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        if video in done:
            # Atraso: se reinicia el codificador, como con "refresh".
            refreshed[0] = asyncio.get_running_loop().time()
            return selected, quality
        return control.result() if control in done else None
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", help="IP Wi-Fi de la PC")
    parser.add_argument("--usb", action="store_true",
                        help="Cable USB con el visor iPad Monitor; junto con --bind, el modo se elige en el iPad")
    parser.add_argument("--monitor", required=True, type=int)
    parser.add_argument("--calidad", choices=("nitida", "fluida"), default="nitida",
                        help="Calidad inicial; el visor puede cambiarla")
    parser.add_argument("--refresco", choices=("intra", "clave"), default="intra" if LINUX else "clave",
                        help="intra: sin cuadros clave periódicos (predeterminado en Linux); "
                             "clave: un cuadro clave cada 2 s, como en Windows")
    parser.add_argument("--preset", choices=PRESETS, default="superfast",
                        help="Preset de x264; ultrafast es el de las versiones anteriores")
    args = parser.parse_args()
    if not args.bind and not args.usb:
        parser.error("Indicá --bind IP, --usb o ambos")
    if LINUX:
        if not os.environ.get("DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            parser.error("La captura en Linux requiere una sesión X11")
        if not shutil.which("ffmpeg"):
            parser.error("Instalá FFmpeg con soporte para x11grab y libx264")
    selected = args.monitor
    quality = "sharp" if args.calidad == "nitida" else "smooth"
    monitors = {item["id"]: item for item in list_monitors() if item["id"] > 0}
    if selected not in monitors:
        parser.error("Elegí un monitor disponible: " + ", ".join(map(str, monitors)))

    # Modo compartido con el visor. Con ambos transportes arranca en Wi-Fi y el
    # iPad pide USB desde su panel; con uno solo, es ese.
    link = {"mode": "wifi" if args.bind else "usb", "usb": None}

    async def stream(reader, writer, usb=False):
        nonlocal selected, quality

        writer.transport.set_write_buffer_limits(high=0)
        entries = [{"id": number, "width": monitor["width"], "height": monitor["height"]}
                   for number, monitor in monitors.items()]
        writer.write(packet(b"monitors=" + json.dumps(entries).encode(), control=True))
        writer.write(packet(cursor_image(), control=True))
        held = set()
        refreshed = [0.0]
        try:
            while True:
                target = await stream_monitor(reader, writer, monitors, selected,
                                              usb, quality, args.preset,
                                              args.refresco == "intra", held, refreshed, link)
                if target is None:
                    return
                if target[0] != selected:
                    print(f"Monitor {target[0]} seleccionado desde el iPad", flush=True)
                if target[1] != quality:
                    print(f"Calidad {'nítida' if target[1] == 'sharp' else 'fluida'} "
                          "seleccionada desde el iPad", flush=True)
                selected, quality = target
        finally:
            input_module().release_buttons(held)

    async def usb_stream(reader, writer):
        # Tarea propia: volver a Wi-Fi la cancela sin detener la espera del cable.
        task = link["usb"] = asyncio.create_task(stream(reader, writer, usb=True))
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            task.cancel()
            raise
        if not task.cancelled():
            task.result()

    async def run():
        servers = []
        if args.usb:
            print(f"iPad Monitor USB | monitor {selected} | 1024x768 | hasta {FPS} FPS", flush=True)
            servers.append(serve_usb(usb_stream, USB_PORT, link=link if args.bind else None))
        if args.bind:
            servers.append(serve(args.bind, selected, FPS, SIZE, stream, 8767, link=link))
        await asyncio.gather(*servers)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
