"""
Routes liées au catalogue : recherche, fetch d'un track, like/dislike.
"""
from flask import Blueprint, jsonify, request, g

from ..auth import login_required
from ..database import execute, query_all, query_one, rows_to_dicts, row_to_dict


bp = Blueprint("tracks", __name__, url_prefix="/api/tracks")


@bp.get("")
def list_tracks():
    """Liste paginée du catalogue avec recherche."""
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    if q:
        like = f"%{q}%"
        rows = query_all(
            """SELECT * FROM tracks
                WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?""",
            (like, like, like, limit, offset),
        )
    else:
        rows = query_all(
            "SELECT * FROM tracks ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return jsonify({"tracks": rows_to_dicts(rows), "count": len(rows)})


@bp.get("/<int:track_id>")
def get_track(track_id: int):
    row = query_one("SELECT * FROM tracks WHERE id = ?", (track_id,))
    if not row:
        return jsonify({"error": "Morceau introuvable"}), 404
    return jsonify(row_to_dict(row))


@bp.post("/<int:track_id>/interact")
@login_required
def interact(track_id: int):
    """Enregistre une interaction (like / dislike / play / skip)."""
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()
    if action not in ("like", "dislike", "play", "skip"):
        return jsonify({"error": "action invalide"}), 400

    if not query_one("SELECT id FROM tracks WHERE id = ?", (track_id,)):
        return jsonify({"error": "Morceau introuvable"}), 404

    execute(
        "INSERT INTO user_interactions (user_id, track_id, action) VALUES (?, ?, ?)",
        (g.user["id"], track_id, action),
    )
    return jsonify({"ok": True, "action": action, "track_id": track_id})


@bp.get("/liked")
@login_required
def liked_tracks():
    """Renvoie les morceaux likés par l'utilisateur (le like le plus récent
    par track gagne s'il y a eu un dislike entretemps)."""
    rows = query_all(
        """SELECT t.*, MAX(ui.created_at) AS liked_at
             FROM user_interactions ui
             JOIN tracks t ON t.id = ui.track_id
            WHERE ui.user_id = ?
              AND ui.action = 'like'
              AND NOT EXISTS (
                    SELECT 1 FROM user_interactions ui2
                     WHERE ui2.user_id = ui.user_id
                       AND ui2.track_id = ui.track_id
                       AND ui2.action = 'dislike'
                       AND ui2.created_at > ui.created_at
              )
            GROUP BY t.id
            ORDER BY liked_at DESC""",
        (g.user["id"],),
    )
    return jsonify(rows_to_dicts(rows))


@bp.delete("/<int:track_id>/like")
@login_required
def unlike(track_id: int):
    """Annule le like d'un morceau (utilisé depuis la page Mes likes)."""
    execute(
        """DELETE FROM user_interactions
            WHERE user_id = ? AND track_id = ? AND action = 'like'""",
        (g.user["id"], track_id),
    )
    return jsonify({"ok": True})


@bp.get("/genres")
def genres():
    rows = query_all(
        """SELECT genre, COUNT(*) AS n
             FROM tracks
            WHERE genre IS NOT NULL
            GROUP BY genre
            ORDER BY n DESC"""
    )
    return jsonify(rows_to_dicts(rows))
