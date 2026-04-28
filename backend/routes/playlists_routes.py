"""
CRUD complet sur les playlists + export Spotify.
"""
from flask import Blueprint, jsonify, request, g

from ..auth import login_required
from ..database import execute, query_all, query_one, rows_to_dicts, row_to_dict
from .. import spotify_client


bp = Blueprint("playlists", __name__, url_prefix="/api/playlists")


def _serialize_playlist(playlist_row: dict) -> dict:
    tracks = query_all(
        """SELECT t.*, pt.position
             FROM playlist_tracks pt
             JOIN tracks t ON t.id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position, pt.added_at""",
        (playlist_row["id"],),
    )
    return {**playlist_row, "tracks": rows_to_dicts(tracks)}


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------
@bp.get("")
@login_required
def list_playlists():
    rows = query_all(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = p.id) AS track_count
             FROM playlists p
            WHERE p.user_id = ?
            ORDER BY p.updated_at DESC""",
        (g.user["id"],),
    )
    playlists = []
    for r in rows:
        d = dict(r)
        playlists.append(_serialize_playlist(d))
    return jsonify(playlists)


@bp.get("/<int:playlist_id>")
@login_required
def get_playlist(playlist_id: int):
    row = query_one(
        "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    )
    if not row:
        return jsonify({"error": "Playlist introuvable"}), 404
    return jsonify(_serialize_playlist(row_to_dict(row)))


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@bp.post("")
@login_required
def create_playlist():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Le nom est requis"}), 400

    description = (data.get("description") or "").strip()
    cover_url = data.get("cover_url")
    pid = execute(
        """INSERT INTO playlists (user_id, name, description, cover_url)
           VALUES (?, ?, ?, ?)""",
        (g.user["id"], name, description, cover_url),
    )
    row = query_one("SELECT * FROM playlists WHERE id = ?", (pid,))
    return jsonify(_serialize_playlist(row_to_dict(row))), 201


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@bp.put("/<int:playlist_id>")
@login_required
def update_playlist(playlist_id: int):
    row = query_one(
        "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    )
    if not row:
        return jsonify({"error": "Playlist introuvable"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or row["name"]).strip()
    description = data.get("description", row["description"])
    cover_url = data.get("cover_url", row["cover_url"])
    execute(
        """UPDATE playlists
              SET name = ?, description = ?, cover_url = ?,
                  updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
        (name, description, cover_url, playlist_id),
    )
    new_row = query_one("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
    return jsonify(_serialize_playlist(row_to_dict(new_row)))


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------
@bp.delete("/<int:playlist_id>")
@login_required
def delete_playlist(playlist_id: int):
    row = query_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    )
    if not row:
        return jsonify({"error": "Playlist introuvable"}), 404
    execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    return jsonify({"ok": True, "deleted": playlist_id})


# ---------------------------------------------------------------------------
# Ajout / suppression de morceaux
# ---------------------------------------------------------------------------
@bp.post("/<int:playlist_id>/tracks")
@login_required
def add_track(playlist_id: int):
    if not query_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    ):
        return jsonify({"error": "Playlist introuvable"}), 404

    data = request.get_json(silent=True) or {}
    track_id = data.get("track_id")
    if not track_id:
        return jsonify({"error": "track_id manquant"}), 400
    if not query_one("SELECT id FROM tracks WHERE id = ?", (track_id,)):
        return jsonify({"error": "Morceau introuvable"}), 404

    # position = max + 1
    pos_row = query_one(
        "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM playlist_tracks WHERE playlist_id = ?",
        (playlist_id,),
    )
    pos = pos_row["pos"] if pos_row else 0
    try:
        execute(
            """INSERT INTO playlist_tracks (playlist_id, track_id, position)
               VALUES (?, ?, ?)""",
            (playlist_id, track_id, pos),
        )
    except Exception:
        return jsonify({"error": "Morceau déjà dans la playlist"}), 409

    execute(
        "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (playlist_id,),
    )
    return jsonify({"ok": True})


@bp.delete("/<int:playlist_id>/tracks/<int:track_id>")
@login_required
def remove_track(playlist_id: int, track_id: int):
    if not query_one(
        "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    ):
        return jsonify({"error": "Playlist introuvable"}), 404
    execute(
        "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, track_id),
    )
    execute(
        "UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (playlist_id,),
    )
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Export vers Spotify
# ---------------------------------------------------------------------------
@bp.post("/<int:playlist_id>/export")
@login_required
def export_to_spotify(playlist_id: int):
    if not g.user.get("spotify_refresh_token"):
        return jsonify({"error": "Connecte ton compte Spotify d'abord"}), 400

    row = query_one(
        "SELECT * FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, g.user["id"]),
    )
    if not row:
        return jsonify({"error": "Playlist introuvable"}), 404

    # On récupère TOUS les morceaux de la playlist avec leurs métadonnées :
    # spotify_id si dispo, sinon titre + artiste pour qu'on cherche à la volée
    tracks = query_all(
        """SELECT t.spotify_id, t.title, t.artist
             FROM playlist_tracks pt
             JOIN tracks t ON t.id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position""",
        (playlist_id,),
    )
    if not tracks:
        return jsonify({"error": "La playlist est vide"}), 400

    try:
        result = spotify_client.export_playlist_to_spotify(
            g.user, row_to_dict(row), rows_to_dicts(tracks)
        )
    except Exception as e:
        msg = str(e)
        # Spotify 403 = compte non autorisé sur l'app en Development Mode
        if "403" in msg or "Forbidden" in msg:
            return (
                jsonify(
                    {
                        "error": (
                            "Spotify a refusé la création (403). "
                            "Ton app est en Development Mode : ajoute ton "
                            "email Spotify dans Dashboard → ton app → User "
                            "Management, puis reconnecte-toi à Spotify."
                        )
                    }
                ),
                403,
            )
        return jsonify({"error": f"Échec de l'export Spotify : {msg}"}), 500

    return jsonify(
        {
            "ok": True,
            "spotify_url": result["url"],
            "matched": result["matched"],
            "total": len(tracks),
            "missing": result["missing"],
        }
    )
