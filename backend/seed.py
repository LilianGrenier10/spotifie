"""
Charge le catalogue depuis data/catalog.csv dans la base SQLite.
Idempotent : INSERT OR REPLACE sur spotify_id.

Usage :
    python -m backend.seed
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import config
from backend.database import init_db, execute_many, query_one


def _coerce(row: dict) -> tuple:
    def num(v, t=float):
        try:
            if v is None or v == "":
                return None
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


def main() -> None:
    init_db()
    csv_path = config.CATALOG_CSV
    if not csv_path.exists():
        print(f"[ERREUR] CSV introuvable : {csv_path}")
        sys.exit(1)

    with csv_path.open(encoding="utf-8") as fh:
        rows = [_coerce(r) for r in csv.DictReader(fh)]

    sql = """
        INSERT OR REPLACE INTO tracks
          (spotify_id, title, artist, album, preview_url, image_url,
           duration_ms, popularity, genre,
           danceability, energy, valence, tempo,
           acousticness, instrumentalness, speechiness, loudness)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    execute_many(sql, rows)

    n = query_one("SELECT COUNT(*) AS n FROM tracks")
    print(f"[OK] {len(rows)} morceaux chargés. Total en BDD : {dict(n)['n']}")


if __name__ == "__main__":
    main()
