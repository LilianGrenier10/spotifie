"""
Enrichit le catalogue avec les VRAIES données Spotify :
    - audio features (danceability, energy, valence, tempo, ...)
    - popularité
    - pochette d'album HD
    - preview_url (quand Spotify le fournit encore — voir note ci-dessous)

⚠️  NOTE TECHNIQUE IMPORTANTE :
    Depuis novembre 2024, Spotify a retiré preview_url de l'API publique
    pour les nouvelles apps. Si vos previews sont vides, lancez ensuite
    `python3 -m backend.enrich_with_itunes` qui les complète via l'API
    iTunes Search (gratuite, publique).

Nécessite : SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET dans backend/.env

Usage :
    python3 -m backend.enrich_with_spotify
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from backend.config import config
from backend.database import execute, query_all, init_db


def main() -> None:
    init_db()

    if not config.spotify_configured():
        print("[ERREUR] Spotify non configuré. Remplis backend/.env d'abord :")
        print("           SPOTIFY_CLIENT_ID=…")
        print("           SPOTIFY_CLIENT_SECRET=…")
        sys.exit(1)

    sp = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=config.SPOTIFY_CLIENT_ID,
            client_secret=config.SPOTIFY_CLIENT_SECRET,
        )
    )

    rows = query_all("SELECT id, spotify_id, title, artist FROM tracks WHERE spotify_id IS NOT NULL")
    if not rows:
        print("[ERREUR] Aucun morceau avec spotify_id en BDD. Lance `python3 -m backend.seed` avant.")
        return

    print(f"==> Enrichissement de {len(rows)} morceaux via l'API Spotify…")
    print()

    spotify_ids = [r["spotify_id"] for r in rows]
    id_to_db = {r["spotify_id"]: r["id"] for r in rows}

    # ----- 1. Métadonnées + pochette + preview -----
    print("    [1/2] Récupération des pochettes et previews…")
    n_with_preview = 0
    for i in range(0, len(spotify_ids), 50):
        chunk = spotify_ids[i : i + 50]
        try:
            res = sp.tracks(chunk)
        except Exception as e:
            print(f"   ! erreur tracks {i}: {e}")
            continue
        for t in res.get("tracks", []):
            if not t:
                continue
            preview = t.get("preview_url")
            img = t["album"]["images"][0]["url"] if t["album"].get("images") else None
            execute(
                """UPDATE tracks
                      SET preview_url = COALESCE(?, preview_url),
                          image_url   = COALESCE(?, image_url),
                          popularity  = ?
                    WHERE id = ?""",
                (preview, img, t.get("popularity") or 50, id_to_db[t["id"]]),
            )
            if preview:
                n_with_preview += 1
    print(f"          ✓ {n_with_preview}/{len(rows)} morceaux ont une preview Spotify")

    # ----- 2. Audio features -----
    print("    [2/2] Récupération des audio features…")
    n_features = 0
    for i in range(0, len(spotify_ids), 100):
        chunk = spotify_ids[i : i + 100]
        try:
            feats = sp.audio_features(chunk)
        except Exception as e:
            print(f"   ! erreur audio_features {i}: {e}")
            print("     (Spotify peut restreindre cet endpoint pour les nouvelles apps —")
            print("      les features synthétiques du CSV resteront utilisables)")
            break
        for f in feats:
            if not f:
                continue
            execute(
                """UPDATE tracks
                      SET danceability=?, energy=?, valence=?, tempo=?,
                          acousticness=?, instrumentalness=?, speechiness=?, loudness=?
                    WHERE id=?""",
                (
                    f["danceability"], f["energy"], f["valence"], f["tempo"],
                    f["acousticness"], f["instrumentalness"], f["speechiness"], f["loudness"],
                    id_to_db[f["id"]],
                ),
            )
            n_features += 1
    print(f"          ✓ {n_features}/{len(rows)} morceaux enrichis avec les vraies audio features")

    print()
    print("==> Enrichissement Spotify terminé.")
    if n_with_preview < len(rows) * 0.5:
        print()
        print("⚠️  Beaucoup de previews manquantes — c'est normal depuis novembre 2024.")
        print("    Lance `python3 -m backend.enrich_with_itunes` pour combler les trous")
        print("    avec l'API iTunes Search (gratuite).")


if __name__ == "__main__":
    main()
