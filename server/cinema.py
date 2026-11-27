"""Videos en streaming y descarga para iPad (MP4 + WebVTT)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException

from server.library import _format_size, library_dir

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov"}
SUBTITLE_EXTENSIONS = {".vtt"}

VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
}


def videos_dir() -> Path:
    root = library_dir() / "videos"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str) -> str:
    if not filename or filename != Path(filename).name:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    if ".." in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    return filename


def _resolve_in_videos(filename: str, allowed_suffixes: set[str]) -> Path:
    name = _safe_filename(filename)
    target = (videos_dir() / name).resolve()
    root = videos_dir()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Archivo no encontrado") from exc
    if not target.is_file() or target.suffix.lower() not in allowed_suffixes:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return target


def resolve_video(filename: str) -> Path:
    return _resolve_in_videos(filename, VIDEO_EXTENSIONS)


def resolve_subtitle(filename: str) -> Path:
    return _resolve_in_videos(filename, SUBTITLE_EXTENSIONS)


def video_mime(path: Path) -> str:
    return VIDEO_MIME.get(path.suffix.lower(), "application/octet-stream")


def find_subtitle(video_path: Path) -> Path | None:
    stem = video_path.stem
    parent = video_path.parent
    exact = parent / f"{stem}.vtt"
    if exact.is_file():
        return exact
    matches = sorted(parent.glob(f"{stem}.*.vtt"))
    if matches:
        return matches[0]
    matches = sorted(parent.glob(f"{stem}_*.vtt"))
    if matches:
        return matches[0]
    return None


def _url_path(prefix: str, filename: str) -> str:
    return f"{prefix}/{quote(filename, safe='')}"


def _video_entry(path: Path) -> dict:
    stat = path.stat()
    subs = find_subtitle(path)
    name = path.name
    entry = {
        "name": name,
        "size": stat.st_size,
        "size_label": _format_size(stat.st_size),
        "has_subs": subs is not None,
        "mime_type": video_mime(path),
        "watch_url": _url_path("/cinema/watch", name),
        "stream_url": _url_path("/cinema/stream", name),
        "download_url": _url_path("/cinema/download", name),
    }
    if subs:
        entry["subs_name"] = subs.name
        entry["subs_url"] = _url_path("/cinema/subs", subs.name)
        entry["subs_download_url"] = _url_path("/cinema/download-subs", subs.name)
    return entry


def list_videos() -> dict:
    root = videos_dir()
    videos = []
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(_video_entry(path))
    return {
        "dir": str(root),
        "count": len(videos),
        "videos": videos,
    }


def video_info(filename: str) -> dict:
    path = resolve_video(filename)
    return _video_entry(path)
