"""
Simple authentication helper for Streamlit app.

Provides user signup and login backed by a local JSON file.

Security notes:
- Uses PBKDF2-HMAC-SHA256 with 100k iterations and a per-user salt.
- Intended for local/small deployments only (not a production auth system).
"""
import json
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional

from config import PROJECT_ROOT


USERS_FILE = PROJECT_ROOT / "data" / "users.json"


def _ensure_users_file():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("{}")


def _load_users():
    _ensure_users_file()
    try:
        return json.loads(USERS_FILE.read_text())
    except Exception:
        return {}


def _save_users(data: dict):
    _ensure_users_file()
    USERS_FILE.write_text(json.dumps(data, indent=2))


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (salt, hex_hash) for given password. If salt is None, generate one."""
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return salt, pwd_hash.hex()


def _find_by_email(users: dict, email: str) -> Optional[str]:
    for uname, meta in users.items():
        if meta.get("email") and meta.get("email").lower() == email.lower():
            return uname
    return None


def create_user(username: str, password: str, display_name: Optional[str] = None, email: Optional[str] = None, is_admin: bool = False) -> tuple[bool, str]:
    users = _load_users()
    if username in users:
        return False, "User already exists"

    if email:
        existing = _find_by_email(users, email)
        if existing:
            return False, "Email already in use"

    salt, pwd_hash = hash_password(password)
    users[username] = {
        "salt": salt,
        "pwd_hash": pwd_hash,
        "display_name": display_name or username,
        "email": email,
        "isadmin": bool(is_admin),
        "created_at": int(time.time()),
    }
    _save_users(users)
    return True, "User created"


def is_admin(username: str) -> bool:
    """Return True if the given username is marked as admin in the users file."""
    users = _load_users()
    u = users.get(username)
    if not u:
        return False
    return bool(u.get("isadmin", False))


def verify_user(username: str, password: str) -> bool:
    users = _load_users()
    u = users.get(username)
    if not u:
        return False
    salt = u.get("salt")
    if not salt:
        return False
    _, pwd_hash = hash_password(password, salt)
    return pwd_hash == u.get("pwd_hash")


def get_display_name(username: str) -> str | None:
    users = _load_users()
    u = users.get(username)
    if not u:
        return None
    return u.get("display_name")


def find_user_by_email(email: str) -> Optional[str]:
    users = _load_users()
    return _find_by_email(users, email)


def create_password_reset(email: str, ttl_seconds: int = 900) -> tuple[bool, str]:
    """Create a password reset code for the user identified by email.

    Returns (True, message) where message is the code for local debugging
    or a generic message on success. If email not found returns (False, msg).
    """
    users = _load_users()
    uname = _find_by_email(users, email)
    if not uname:
        return False, "No account with that email"

    # 6-digit numeric code
    code = str(secrets.randbelow(900000) + 100000)
    expires = int(time.time()) + int(ttl_seconds)
    users[uname]["reset_code"] = code
    users[uname]["reset_expires"] = expires
    _save_users(users)
    # For local debugging we return the code; in production you would not.
    return True, code


def verify_password_reset(email: str, code: str, new_password: str) -> tuple[bool, str]:
    users = _load_users()
    uname = _find_by_email(users, email)
    if not uname:
        return False, "No account with that email"

    u = users.get(uname)
    if not u:
        return False, "Account not found"

    expected = u.get("reset_code")
    expires = u.get("reset_expires", 0)
    if not expected or int(time.time()) > int(expires):
        return False, "Reset code expired or not found"

    if str(code).strip() != str(expected).strip():
        return False, "Invalid reset code"

    # All good — set new password and clear reset fields
    salt, pwd_hash = hash_password(new_password)
    u["salt"] = salt
    u["pwd_hash"] = pwd_hash
    u.pop("reset_code", None)
    u.pop("reset_expires", None)
    _save_users(users)
    return True, "Password updated"


def list_users() -> list:
    return list(_load_users().keys())
