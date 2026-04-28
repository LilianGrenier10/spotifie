"""
Import de catalogue CSV (admin) + reset du catalogue.

Format CSV attendu :
    spotify_id,title,artist,album,preview_url,image_url,duration_ms,popularity,
    genre,danceability,energy,valence,tempo,acousticness,instrumentalness,
    speechiness,loudness
"""
import csv
import io

from flask import Blueprint, jsonify, request

from ..database import execute, execute_many, query_one


bp = Blueprint("catalog", __name__, url_prefix="/api/catalog")


CSV_FIELDS = [
    "spotify_id", "title", "artist", "album", "preview_url", "image_url",
    "duration_ms", "popularity", "genre",
    "danceability", "energy", "valence", "tempo",
    "acousticness", "instrumentalness", "speechiness", "loudness",
]


def _coerce(row: dict) -> tuple:
    def num(v, t=float):
        try:
            return t(v)
        except (TypeError, ValueError):
            return None

    return (
        row.get("spotify_id") or None,
        row.get("title") or "",
        row.get("artist") or "",
        row.get("album") or None,
        row.get("preview_url") or None,
        row.get("image_url") or None,
        num(row.get("duration_ms"), int),
        num(row.get("popularity"), int) or 50,
        row.get("genre") or None,
        num(row.get("danceability")),
        num(row.get("energy")),
        num(row.get("valence")),
        num(row.get("tempo")),
        num(row.get("acousticness")),
        num(row.get("instrumentalness")),
        num(row.get("speechiness")),
        num(row.get("loudness")),
    )


@bp.post("/import")
def import_csv():
    """Importe un CSV depuis le body (form-data ou raw text)."""
    if "file" in request.files:
        text = request.files["file"].read().decode("utf-8")
    else:
        text = request.get_data(as_text=True)
    if not text.strip():
        return jsonify({"error": "Aucune donnée CSV reçue"}), 400

    reader = csv.DictReader(io.StringIO(text))
    rows = [_coerce(r) for r in reader]
    if not rows:
        return jsonify({"error": "CSV vide"}), 400

    sql = f"""
        INSERT OR REPLACE INTO tracks
          (spotify_id, title, artist, album, preview_url, image_url,
           duration_ms, popularity, genre,
           danceability, energy, valence, tempo,
           acousticness, instrumentalness, speechiness, loudness)
        VALUES ({','.join(['?'] * len(CSV_FIELDS))})
    """
    execute_many(sql, rows)
    n = query_one("SELECT COUNT(*) AS n FROM tracks")
    return jsonify({"imported": len(rows), "total": dict(n)["n"]})
