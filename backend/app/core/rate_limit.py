"""Rate limiting en memoria — suficiente para un servidor VPS single-process."""
from collections import defaultdict
from threading import Lock
from time import time
from typing import Optional

from fastapi import HTTPException, status

_lock = Lock()
_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 10
WINDOW_SECONDS = 15 * 60   # 15 minutos


def check(key: str) -> None:
    now = time()
    with _lock:
        valid = [t for t in _attempts[key] if now - t < WINDOW_SECONDS]
        _attempts[key] = valid
        if len(valid) >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Espera {WINDOW_SECONDS // 60} minutos.",
            )
        _attempts[key].append(now)


def reset(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)
