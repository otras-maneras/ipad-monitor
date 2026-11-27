"""Biblioteca de libros (EPUB/PDF) servida al iPad para iBooks."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from server.settings import load_config

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_EXTENSIONS = {".epub", ".pdf"}

MIME_TYPES = {
    ".epub": "application/epub+zip",
    ".pdf": "application/pdf",
}


def library_dir() -> Path:
    cfg = load_config()
    rel = cfg.get("library_dir") or "library"
    base = Path(rel)
    if not base.is_absolute():
        base = ROOT / base
    resolved = base.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def _is_allowed(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS


def resolve_book(filename: str) -> Path:
    if not filename or filename != Path(filename).name:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    if ".." in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")

    target = (library_dir() / filename).resolve()
    root = library_dir()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Archivo no encontrado") from exc

    if not _is_allowed(target):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return target


def mime_type(path: Path) -> str:
    return MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def list_books() -> dict:
    root = library_dir()
    books = []
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not _is_allowed(path):
            continue
        ext = path.suffix.lower().lstrip(".")
        stat = path.stat()
        books.append(
            {
                "name": path.name,
                "kind": ext,
                "size": stat.st_size,
                "size_label": _format_size(stat.st_size),
                "url": f"/library/download/{path.name}",
            }
        )
    return {
        "dir": str(root),
        "count": len(books),
        "books": books,
    }
