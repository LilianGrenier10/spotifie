"""
Authentification : hashing bcrypt + JWT + décorateur de route protégée.
"""
from __future__ import annotations

import datetime as dt
from functools import wraps
from typing import Callable, Optional

import bcrypt
import jwt
from flask import request, jsonify, g

from .config import config
from .database import query_one, row_to_dict


# ---------------------------------------------------------------------------
# Mots de passe
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Bcrypt avec salt automatique."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def make_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": dt.datetime.now(dt.timezone.utc)
        + dt.timedelta(hours=config.JWT_EXP_HOURS),
        "iat": dt.datetime.now(dt.timezone.utc),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def _extract_token() -> Optional[str]:
    """Cherche le JWT dans l'en-tête Authorization OU le cookie 'token'."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("token")


def current_user() -> Optional[dict]:
    """Renvoie l'utilisateur courant ou None."""
    token = _extract_token()
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user = query_one("SELECT * FROM users WHERE id = ?", (payload["user_id"],))
    return row_to_dict(user)


def login_required(fn: Callable) -> Callable:
    """Décorateur : refuse 401 si l'utilisateur n'est pas connecté."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Authentification requise"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper
