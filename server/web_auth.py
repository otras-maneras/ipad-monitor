"""PIN del modo web.

Al arrancar, el servidor muestra un PIN de 4 cifras. Un navegador que lo
ingresa recibe una cookie de sesión que se guarda en disco, así no vuelve a
pedirlo aunque se reinicie el servidor. Sin esa cookie, las páginas llevan a
/login y la API responde 401.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

COOKIE = "ipm_sesion"
# Un año: Safari de iOS 9 conserva la cookie entre visitas y en los accesos
# de la pantalla de inicio, que tienen su propio almacén.
COOKIE_MAX_AGE = 365 * 24 * 3600
# Rutas que se pueden abrir sin sesión.
PUBLIC_PATHS = ("/login", "/api/login", "/static/style.css", "/static/app.js", "/favicon.ico")
MAX_FAILURES = 5
LOCK_SECONDS = 60


def _config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "ipad-monitor"


class WebAuth:
    def __init__(self, path: Path | None = None) -> None:
        self.pin = f"{secrets.randbelow(10000):04d}"
        self.path = path or _config_dir() / "web-sesiones.json"
        self.sessions = self._load()
        self.failures: dict[str, tuple[int, float]] = {}

    def _load(self) -> set[str]:
        try:
            data = json.loads(self.path.read_text())
            return {token for token in data if isinstance(token, str) and len(token) == 43}
        except (OSError, ValueError, TypeError):
            return set()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.touch(mode=0o600)
            temporary.write_text(json.dumps(sorted(self.sessions)))
            os.replace(temporary, self.path)
        except OSError as error:
            print(f"No se pudo guardar la sesión web: {error}", flush=True)

    def valid(self, token: str | None) -> bool:
        return bool(token) and any(hmac.compare_digest(token, known) for known in self.sessions)

    def locked(self, address: str) -> bool:
        count, until = self.failures.get(address, (0, 0.0))
        if until and until <= time.monotonic():
            self.failures.pop(address, None)
            return False
        return count >= MAX_FAILURES

    def login(self, address: str, pin: str) -> str | None:
        """Devuelve un token de sesión nuevo si el PIN es correcto."""
        if self.locked(address):
            return None
        if not hmac.compare_digest(pin.strip(), self.pin):
            count, _ = self.failures.get(address, (0, 0.0))
            count += 1
            self.failures[address] = (count, time.monotonic() + LOCK_SECONDS if count >= MAX_FAILURES else 0.0)
            return None
        self.failures.pop(address, None)
        token = secrets.token_urlsafe(32)
        self.sessions.add(token)
        self._save()
        return token

    @staticmethod
    def is_public(path: str) -> bool:
        return path in PUBLIC_PATHS
