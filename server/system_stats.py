import platform
import socket
import time
from datetime import datetime

import psutil

from server.network import list_local_ips, preferred_ip
from server import screen_capture


def _bytes_human(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value:.0f} B"


def _seconds_human(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _disk_stats() -> list[dict]:
    disks = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts.lower():
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append(
            {
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "total_human": _bytes_human(usage.total),
                "used_human": _bytes_human(usage.used),
                "free_human": _bytes_human(usage.free),
            }
        )
    return disks


def _network_stats() -> dict:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io = psutil.net_io_counters()
    interfaces = []

    for name, entries in addrs.items():
        stat = stats.get(name)
        if not stat or not stat.isup:
            continue
        ipv4 = [a.address for a in entries if a.family == socket.AF_INET]
        if not ipv4:
            continue
        interfaces.append(
            {
                "name": name,
                "ipv4": ipv4,
                "speed_mbps": stat.speed if stat.speed > 0 else None,
            }
        )

    return {
        "bytes_sent": io.bytes_sent,
        "bytes_recv": io.bytes_recv,
        "packets_sent": io.packets_sent,
        "packets_recv": io.packets_recv,
        "errors_in": io.errin,
        "errors_out": io.errout,
        "bytes_sent_human": _bytes_human(io.bytes_sent),
        "bytes_recv_human": _bytes_human(io.bytes_recv),
        "interfaces": interfaces,
        "local_ips": list_local_ips(),
        "preferred_ip": preferred_ip(),
    }


def _battery_stats() -> dict | None:
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, OSError):
        return None
    if not battery:
        return None

    secs = battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
    return {
        "percent": battery.percent,
        "plugged": battery.power_plugged,
        "time_left_seconds": secs,
        "time_left_human": _seconds_human(secs) if secs and secs > 0 else None,
    }


def _cpu_stats() -> dict:
    freq = psutil.cpu_freq()
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    return {
        "percent": round(sum(per_core) / max(len(per_core), 1), 1),
        "cores_physical": psutil.cpu_count(logical=False) or 0,
        "cores_logical": psutil.cpu_count(logical=True) or 0,
        "per_core": [round(v, 1) for v in per_core],
        "freq_mhz": round(freq.current, 0) if freq else None,
        "freq_max_mhz": round(freq.max, 0) if freq and freq.max else None,
    }


def _top_processes(limit: int = 5) -> list[dict]:
    ranked = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            info = proc.info
            ranked.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name") or "?",
                    "cpu_percent": 0.0,
                    "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    ranked.sort(key=lambda p: p["memory_percent"], reverse=True)
    return ranked[:limit]


def _memory_stats() -> dict:
    mem = psutil.virtual_memory()
    swap_percent = 0.0
    swap_used = 0
    swap_total = 0
    try:
        swap = psutil.swap_memory()
        swap_percent = swap.percent
        swap_used = swap.used
        swap_total = swap.total
    except (RuntimeError, OSError):
        pass

    return {
        "percent": mem.percent,
        "total": mem.total,
        "used": mem.used,
        "available": mem.available,
        "total_human": _bytes_human(mem.total),
        "used_human": _bytes_human(mem.used),
        "available_human": _bytes_human(mem.available),
        "swap_percent": swap_percent,
        "swap_used_human": _bytes_human(swap_used),
        "swap_total_human": _bytes_human(swap_total),
    }


def _temperature_stats() -> list[dict]:
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return []

    readings = []
    for name, entries in temps.items():
        for entry in entries:
            if entry.current is None:
                continue
            readings.append(
                {
                    "label": entry.label or name,
                    "current": round(entry.current, 1),
                }
            )
    return readings[:6]


def gather_stats() -> dict:
    boot = psutil.boot_time()
    uptime = time.time() - boot

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "uptime_seconds": int(uptime),
        "uptime_human": _seconds_human(uptime),
        "boot_time": datetime.fromtimestamp(boot).isoformat(timespec="seconds"),
        "process_count": len(psutil.pids()),
        "cpu": _cpu_stats(),
        "memory": _memory_stats(),
        "disks": _disk_stats(),
        "network": _network_stats(),
        "battery": _battery_stats(),
        "temperatures": _temperature_stats(),
        "top_processes": _top_processes(),
        "stream": screen_capture.engine.stats(),
    }
