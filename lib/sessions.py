"""
Simple file-backed session store.

Stores opaque session_id -> {user, created_at, expires_at} mappings in
`data/sessions.json`. Intended for local/dev use. Sessions are referenced
by an opaque UUID stored in a cookie on the client.
"""
from pathlib import Path
import json
import time
import secrets
from typing import Optional

from config import PROJECT_ROOT


SESSIONS_FILE = PROJECT_ROOT / "data" / "sessions.json"


def _ensure_file():
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_FILE.exists():
        SESSIONS_FILE.write_text("{}")


def _load():
    _ensure_file()
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict):
    _ensure_file()
    SESSIONS_FILE.write_text(json.dumps(data, indent=2))


def create_session(user: str, ttl_seconds: int = 86400) -> str:
    """Create a new session for `user`. Returns the opaque session_id."""
    sid = secrets.token_urlsafe(32)
    now = int(time.time())
    sessions = _load()
    sessions[sid] = {
        "user": user,
        "created_at": now,
        "expires_at": now + int(ttl_seconds),
    }
    _save(sessions)
    return sid


def get_session(sid: str) -> Optional[dict]:
    sessions = _load()
    s = sessions.get(sid)
    if not s:
        return None
    if int(time.time()) > int(s.get("expires_at", 0)):
        # expired — remove and return None
        delete_session(sid)
        return None
    return s


def delete_session(sid: str) -> None:
    sessions = _load()
    if sid in sessions:
        sessions.pop(sid, None)
        _save(sessions)


def cleanup_expired() -> int:
    sessions = _load()
    now = int(time.time())
    removed = 0
    for k, v in list(sessions.items()):
        if int(v.get("expires_at", 0)) < now:
            sessions.pop(k, None)
            removed += 1
    if removed:
        _save(sessions)
    return removed
