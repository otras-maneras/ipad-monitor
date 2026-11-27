import socket


def _is_private_ip(ip: str) -> bool:
    if ip.startswith("192.168."):
        return True
    if ip.startswith("172."):
        parts = ip.split(".")
        if len(parts) > 1 and parts[1].isdigit():
            return 16 <= int(parts[1]) <= 31
    return ip.startswith("10.")


def list_local_ips() -> list[str]:
    ips: set[str] = set()

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass

    try:
        import psutil

        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ips.add(addr.address)
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ips.add(sock.getsockname()[0])
    except OSError:
        pass

    ordered = sorted(ips, key=lambda ip: (0 if ip.startswith("192.168.") else 1, ip))
    return ordered


def preferred_ip() -> str:
    ips = list_local_ips()
    if not ips:
        return "127.0.0.1"

    for ip in ips:
        if ip.startswith("192.168."):
            return ip

    for ip in ips:
        if _is_private_ip(ip):
            return ip

    return ips[0]
