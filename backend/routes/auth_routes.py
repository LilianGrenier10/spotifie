"""
Routes d'authentification : register, login, logout, OAuth Spotify.
"""
from __future__ import annotations

import secrets

from flask import Blueprint, jsonify, request, redirect, make_response, g

from ..auth import (
    hash_password,
    verify_password,
    make_token,
    login_required,
    current_user,
)
from ..config import config
from ..database import execute, query_one, row_to_dict
from .. import spotify_client


bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# stockage en mémoire du mapping state -> user_id (suffisant pour la démo)
_OAUTH_STATES: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Inscription
# ---------------------------------------------------------------------------
@bp.post("/register")
def register():
    data = request.get_json(silent=True) or request.form.to_dict()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or email.split("@")[0]).strip()

    if not email or not password:
        return jsonify({"error": "Email et mot de passe requis"}), 400
    if len(password) < 6:
        return jsonify({"error": "Mot de passe trop court (min 6)"}), 400

    if query_one("SELECT id FROM users WHERE email = ?", (email,)):
        return jsonify({"error": "Cet email est déjà utilisé"}), 409

    user_id = execute(
        "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
        (email, hash_password(password), display_name),
    )

    token = make_token(user_id)
    resp = make_response(
        jsonify(
            {
                "user": {"id": user_id, "email": email, "display_name": display_name},
                "token": token,
            }
        )
    )
    resp.set_cookie("token", token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 7)
    return resp


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------
@bp.post("/login")
def login():
    data = request.get_json(silent=True) or request.form.to_dict()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user_row = query_one("SELECT * FROM users WHERE email = ?", (email,))
    user = row_to_dict(user_row)
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Identifiants invalides"}), 401

    token = make_token(user["id"])
    resp = make_response(
        jsonify(
            {
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "display_name": user["display_name"],
                    "spotify_connected": bool(user.get("spotify_id")),
                },
                "token": token,
            }
        )
    )
    resp.set_cookie("token", token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 7)
    return resp


# ---------------------------------------------------------------------------
# Déconnexion
# ---------------------------------------------------------------------------
@bp.post("/logout")
def logout():
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("token")
    return resp


# ---------------------------------------------------------------------------
# Profil courant
# ---------------------------------------------------------------------------
@bp.get("/me")
@login_required
def me():
    u = g.user
    return jsonify(
        {
            "id": u["id"],
            "email": u["email"],
            "display_name": u["display_name"],
            "spotify_connected": bool(u.get("spotify_id")),
            "spotify_id": u.get("spotify_id"),
            "exotic_factor": u.get("exotic_factor"),
        }
    )


@bp.post("/preferences")
@login_required
def update_prefs():
    data = request.get_json(silent=True) or {}
    factor = data.get("exotic_factor")
    if factor is None:
        return jsonify({"error": "exotic_factor manquant"}), 400
    try:
        f = float(factor)
        f = max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return jsonify({"error": "exotic_factor invalide"}), 400
    execute("UPDATE users SET exotic_factor = ? WHERE id = ?", (f, g.user["id"]))
    return jsonify({"exotic_factor": f})


# ---------------------------------------------------------------------------
# Spotify OAuth
# ---------------------------------------------------------------------------
@bp.get("/spotify/login")
@login_required
def spotify_login():
    if not config.spotify_configured():
        return jsonify({"error": "Spotify non configuré côté serveur"}), 503
    state = secrets.token_urlsafe(24)
    _OAUTH_STATES[state] = g.user["id"]
    return redirect(spotify_client.authorize_url(state=state))


@bp.get("/spotify/callback")
def spotify_callback():
    state = request.args.get("state", "")
    code = request.args.get("code")
    if not code or state not in _OAUTH_STATES:
        return "Erreur OAuth (state invalide)", 400

    user_id = _OAUTH_STATES.pop(state)
    try:
        token_info = spotify_client.exchange_code(code)
        me_info = spotify_client.get_me(token_info["access_token"])
        spotify_client.save_tokens_to_user(user_id, token_info, me_info["id"])
    except Exception as e:  # pragma: no cover
        return f"Erreur OAuth Spotify : {e}", 500

    # Redirige vers la page profil avec un flag de succès
    return redirect("/profil.html?spotify=ok")


@bp.post("/spotify/disconnect")
@login_required
def spotify_disconnect():
    execute(
        """UPDATE users
              SET spotify_id = NULL,
                  spotify_access_token = NULL,
                  spotify_refresh_token = NULL,
                  spotify_token_expires_at = NULL
            WHERE id = ?""",
        (g.user["id"],),
    )
    return jsonify({"ok": True})
