"""Enlace con el visor: emparejamiento con PIN, Wi-Fi y USB (usbmuxd o Apple Mobile Device)."""

import asyncio
import hmac
import json
import os
import plistlib
import re
import secrets
import socket
import struct
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from server.config import IPAD_HEIGHT, IPAD_WIDTH


USBMUXD_SOCKET = "/var/run/usbmuxd"


def packet(payload: bytes, control: bool = False) -> bytes:
    return struct.pack("!I", len(payload) | (0x80000000 if control else 0)) + payload


def proof(key: bytes, role: str, client_nonce: str, server_nonce: str) -> str:
    return hmac.digest(key, f"{role}:{client_nonce}:{server_nonce}".encode(), "sha256").hex()


async def mux_request(reader, writer, message_type, **fields):
    payload = plistlib.dumps({"MessageType": message_type,
                              "ClientVersionString": "iPad Monitor", **fields})
    writer.write(struct.pack("<4I", 16 + len(payload), 1, 8, 1) + payload)
    await writer.drain()
    length, version, kind, tag = struct.unpack("<4I", await reader.readexactly(16))
    if (version, kind, tag) != (1, 8, 1) or not 16 < length <= 1024 * 1024:
        raise OSError("Respuesta inesperada del servicio USB de Apple")
    return plistlib.loads(await reader.readexactly(length - 16))


async def serve_usb(video_stream, port, link=None):
    """link: modo compartido con el visor ({"mode": "wifi" | "usb"}). En modo Wi-Fi
    no se abre el enlace USB; el visor pide USB desde su panel."""
    last_error = None
    while True:
        writer = None
        if link is not None and link["mode"] != "usb":
            await asyncio.sleep(1)
            continue
        try:
            async with asyncio.timeout(5):
                if sys.platform.startswith("linux"):
                    # usbmuxd arranca solo cuando el sistema detecta el iPad por cable.
                    if not os.path.exists(USBMUXD_SOCKET):
                        raise OSError("Esperando el iPad por USB: usbmuxd todavía no está activo")
                    reader, writer = await asyncio.open_unix_connection(USBMUXD_SOCKET, limit=8192)
                else:
                    reader, writer = await asyncio.open_connection("127.0.0.1", 27015, limit=8192)
                response = await mux_request(reader, writer, "ListDevices")
                devices = [device for device in response.get("DeviceList", [])
                           if device.get("Properties", {}).get("ConnectionType") == "USB"]
                if len(devices) != 1:
                    raise OSError(f"Dispositivos Apple por USB: {len(devices)}. Conectá solo el iPad.")
                response = await mux_request(reader, writer, "Connect",
                                             DeviceID=devices[0]["DeviceID"],
                                             PortNumber=socket.htons(port))
                if response.get("Number") != 0:
                    raise OSError(f"El visor USB no responde ({response.get('Number')}). Abrí iPad Monitor en el iPad.")
                writer.write(struct.pack("!8sII", b"IPSCRN03", IPAD_WIDTH, IPAD_HEIGHT))
                writer.write(packet(b"mode=usb", control=True))
                await writer.drain()
                while not (hello := await reader.readuntil(b"\n")).startswith(b"hello "):
                    pass
                if not re.fullmatch(rb"hello id=[0-9a-f]{32}( pair)?", hello.strip()):
                    raise OSError("Identidad USB inesperada del visor")
            print("Visor conectado por USB a 1024x768", flush=True)
            last_error = None
            await video_stream(reader, writer)
        except (OSError, EOFError, ValueError, asyncio.LimitOverrunError) as error:
            if isinstance(error, (EOFError, ConnectionError)):
                message = "Se cortó el enlace USB"
            else:
                message = str(error) or "Tiempo de espera agotado en el enlace USB"
            if message != last_error:
                print(message, flush=True)
                last_error = message
        finally:
            if writer is not None:
                writer.close()
        await asyncio.sleep(2)


async def authenticate(reader, writer, pin, keys, failures, address, size, mode="wifi"):
    request = await reader.readuntil(b"\r\n\r\n")
    method, target, _ = request.split(b"\r\n", 1)[0].decode("ascii").split()
    url = urlsplit(target)
    query = parse_qs(url.query)
    device, nonce = (query.get(field, [""])[0] for field in ("id", "cn"))
    if method != "GET" or url.path != "/raw":
        print(f"{address}: solicitud fuera de /raw", flush=True)
        return False
    if not all(re.fullmatch("[0-9a-f]{32}", value) for value in (device, nonce)):
        print(f"{address}: identidad o nonce inválido (longitudes {len(device)}, {len(nonce)})", flush=True)
        return False

    header = struct.pack("!8sII", b"IPSCRN03", *size)
    now = asyncio.get_running_loop().time()
    for expired in [ip for ip, (_, end) in failures.items() if end <= now]:
        del failures[expired]
    count, _ = failures.get(address, (0, 0))
    if count >= 5:
        writer.write(header + packet(b"auth=locked", control=True))
        await writer.drain()
        return False

    server_nonce = secrets.token_hex(16)
    key = keys.get(device)
    if key is None:
        challenge = f"pin={server_nonce}"
        reply_prefix = b"pin="
        expected = "pin=" + proof(pin, "P", nonce, server_nonce)
    else:
        challenge = f"hello={server_nonce}:{proof(key, 'S', nonce, server_nonce)}"
        reply_prefix = b"proof="
        expected = "proof=" + proof(key, "C", nonce, server_nonce)
    writer.write(header + packet(challenge.encode(), control=True))
    await writer.drain()
    print(f"{address}: {'solicitando PIN' if key is None else 'verificando clave'}", flush=True)

    while line := await reader.readline():
        response = line.rstrip(b"\r\n")
        # The native client can send mode or heartbeat before its auth reply.
        if not response.startswith(reply_prefix):
            continue
        if not hmac.compare_digest(response, expected.encode()):
            print(f"{address}: autenticación rechazada", flush=True)
            failures[address] = (count + 1, asyncio.get_running_loop().time() + 60)
            writer.write(packet(b"auth=wrong", control=True))
            await writer.drain()
            return False
        if key is None:
            key = keys[device] = secrets.token_bytes(32)
            writer.write(packet(f"key={key.hex()}".encode(), control=True))
        failures.pop(address, None)
        writer.write(packet(f"mode={mode}".encode(), control=True))
        await writer.drain()
        return True
    return False


def keys_path():
    """Archivo con las claves de los visores emparejados, fuera del proyecto."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "ipad-monitor" / "ipadscreen-claves.json"


def load_keys(path):
    """Claves guardadas: así un visor ya emparejado no vuelve a pedir el PIN."""
    if not path.exists():
        # El proyecto se llamaba MiniPad: se aprovechan las claves de entonces.
        old = path.parent.parent / "minipad" / path.name
        if old.exists():
            path = old
    try:
        stored = json.loads(path.read_text())
        return {device: bytes.fromhex(key) for device, key in stored.items()
                if re.fullmatch("[0-9a-f]{32}", device) and re.fullmatch("[0-9a-f]{64}", key)}
    except (OSError, ValueError, AttributeError):
        return {}


def save_keys(path, keys):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.touch(mode=0o600)
        temporary.write_text(json.dumps({device: key.hex() for device, key in keys.items()}))
        os.replace(temporary, path)
    except OSError as error:
        print(f"No se pudo guardar la clave del visor: {error}", flush=True)


async def serve(bind, monitor, fps, size, video_stream, port, link=None):
    pin = f"{secrets.randbelow(10000):04d}"
    stored = keys_path()
    keys = load_keys(stored)
    failures = {}
    current = None
    pending = 0

    async def handle(reader, writer):
        nonlocal current, pending
        # Pocas autenticaciones a la vez; el visor activo no se toca hasta que
        # el nuevo demuestre que conoce el PIN o la clave.
        if pending >= 4:
            writer.close()
            return
        pending += 1
        address = writer.get_extra_info("peername")[0]
        streaming = False
        try:
            try:
                async with asyncio.timeout(10):
                    known = len(keys)
                    paired = await authenticate(reader, writer, pin.encode(), keys, failures, address, size,
                                                link["mode"] if link else "wifi")
            finally:
                pending -= 1
            if paired:
                if len(keys) != known:
                    save_keys(stored, keys)
                # Al reconectarse tras un corte de Wi-Fi, el enlace anterior puede
                # seguir abierto hasta que venza su latido. El nuevo lo reemplaza
                # en lugar de quedar rechazado.
                previous, current = current, asyncio.current_task()
                streaming = True
                if previous is not None and not previous.done():
                    print(f"{address}: reemplaza el enlace anterior", flush=True)
                    previous.cancel()
                    await asyncio.gather(previous, return_exceptions=True)
                print(f"Visor conectado desde {address}", flush=True)
                await video_stream(reader, writer)
        except TimeoutError:
            print(f"{address}: tiempo de espera agotado", flush=True)
        except OSError as error:
            if str(error):
                print(f"{address}: {error}", flush=True)
        except (EOFError, ValueError, asyncio.LimitOverrunError):
            pass
        except Exception as error:
            print(f"Error en el emisor: {error}", flush=True)
        finally:
            writer.close()
            if streaming and current is asyncio.current_task():
                current = None

    async with await asyncio.start_server(handle, bind, port, limit=4096) as listener:
        print(f"iPad Monitor Wi-Fi {bind}:{port} | monitor {monitor} | "
              f"{size[0]}x{size[1]} | {fps} FPS | PIN {pin}",
              flush=True)
        print(f"\n  >>> PIN: {pin} <<<   (IP {bind})\n", flush=True)
        await listener.serve_forever()

