import json
from pathlib import Path
from typing import Any

from server.config import DEFAULT_CAPTURE, DEFAULT_PRESET, QUALITY_PRESETS

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

_cache: dict[str, Any] | None = None
_cache_mtime: float = 0.0


def _defaults() -> dict[str, Any]:
    preset = QUALITY_PRESETS[DEFAULT_PRESET]
    return {
        "capture": dict(DEFAULT_CAPTURE),
        "preset": DEFAULT_PRESET,
        "jpeg_quality": preset["jpeg_quality"],
        "target_fps": preset["target_fps"],
        "resize_method": preset["resize_method"],
        "jpeg_subsample": preset["jpeg_subsample"],
        "library_dir": "library",
        "config_version": 0,
    }


def _read_config_file() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return _defaults()

    with CONFIG_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)

    merged = _defaults()
    merged["capture"] = {**merged["capture"], **data.get("capture", {})}
    merged["config_version"] = int(data.get("config_version") or 0)

    for key in ("preset", "jpeg_quality", "target_fps", "resize_method", "jpeg_subsample", "library_dir"):
        if key in data and data[key] is not None:
            merged[key] = data[key]

    return merged


def load_config() -> dict[str, Any]:
    global _cache, _cache_mtime
    mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0
    if _cache is not None and mtime == _cache_mtime:
        return _cache

    _cache = _read_config_file()
    _cache_mtime = mtime
    return _cache


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    global _cache, _cache_mtime
    current = load_config()

    if "capture" in updates:
        current["capture"] = {**current["capture"], **updates["capture"]}

    for key in ("preset", "jpeg_quality", "target_fps", "resize_method", "jpeg_subsample", "library_dir"):
        if key in updates and updates[key] is not None:
            current[key] = updates[key]

    current["config_version"] = int(current.get("config_version") or 0) + 1

    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2)

    _cache = current
    _cache_mtime = CONFIG_PATH.stat().st_mtime
    return current


def save_capture(capture: dict[str, Any]) -> dict[str, Any]:
    current = save_config({"capture": capture})
    return current["capture"]


def apply_preset(name: str) -> dict[str, Any]:
    if name not in QUALITY_PRESETS:
        raise ValueError(f"Preset desconocido: {name}")

    preset = QUALITY_PRESETS[name]
    return save_config(
        {
            "preset": name,
            "jpeg_quality": preset["jpeg_quality"],
            "target_fps": preset["target_fps"],
            "resize_method": preset["resize_method"],
            "jpeg_subsample": preset["jpeg_subsample"],
        }
    )
