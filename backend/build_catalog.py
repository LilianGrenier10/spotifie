"""
Construit un catalogue ÉNORME (~1000 morceaux) en interrogeant l'API
iTunes Search sur de nombreux genres, époques et thématiques.

Chaque morceau récupéré contient déjà :
    - preview_url 30s
    - pochette HD
    - durée
    - métadonnées (titre, artiste, album)

Les audio features (danceability, energy, ...) sont synthétisées par genre
sur des plages musicalement plausibles — l'algo de reco fonctionne ainsi
avec des clusters cohérents par genre, sans dépendre de l'API Spotify.

Utilisation :
    python3 -m backend.build_catalog          # ajoute au catalogue existant
    python3 -m backend.build_catalog --reset  # vide d'abord la table tracks
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import init_db, execute, execute_many, query_one


ITUNES_URL = "https://itunes.apple.com/search"
BASE_DELAY = 0.6           # délai entre 2 requêtes
PER_QUERY_LIMIT = 50       # max de morceaux iTunes par requête (max iTunes = 200)


# ---------------------------------------------------------------------------
# Liste de requêtes par genre — chaque genre est exploré sous plusieurs angles
# pour récupérer une variété maximale (classiques, années, sous-genres).
# ---------------------------------------------------------------------------
GENRE_QUERIES: list[tuple[str, str]] = [
    # Pop
    ("pop", "pop hits"),
    ("pop", "pop 2024"),
    ("pop", "pop 2023"),
    ("pop", "pop 2010s"),
    ("pop", "teen pop"),
    ("pop", "pop ballad"),
    # Rock
    ("rock", "rock classics"),
    ("rock", "alternative rock"),
    ("rock", "rock 90s"),
    ("rock", "indie rock"),
    ("rock", "british rock"),
    ("rock", "rock 2020"),
    # Hip-Hop / Rap
    ("hip-hop", "hip hop hits"),
    ("hip-hop", "rap classics"),
    ("hip-hop", "trap music"),
    ("hip-hop", "old school hip hop"),
    ("hip-hop", "hip hop 2024"),
    # Electronic / EDM
    ("electronic", "electronic dance"),
    ("electronic", "edm hits"),
    ("electronic", "house music"),
    ("electronic", "techno"),
    ("electronic", "drum and bass"),
    # Indie
    ("indie", "indie hits"),
    ("indie", "indie folk"),
    ("indie", "indie pop"),
    ("indie", "bedroom pop"),
    # Metal
    ("metal", "heavy metal"),
    ("metal", "metal classics"),
    ("metal", "thrash metal"),
    # Classical
    ("classical", "classical piano"),
    ("classical", "classical symphony"),
    ("classical", "baroque music"),
    ("classical", "classical violin"),
    # Jazz
    ("jazz", "jazz standards"),
    ("jazz", "smooth jazz"),
    ("jazz", "jazz fusion"),
    ("jazz", "bebop"),
    # Country
    ("country", "country hits"),
    ("country", "country classics"),
    # R&B / Soul
    ("r&b", "rnb hits"),
    ("r&b", "soul music"),
    ("r&b", "neo soul"),
    # Latin
    ("latin", "reggaeton"),
    ("latin", "latin pop"),
    ("latin", "bachata"),
    ("latin", "salsa"),
    # Funk / Disco
    ("funk", "funk classics"),
    ("funk", "disco hits"),
    # Synthwave / Retro
    ("synthwave", "synthwave"),
    ("synthwave", "retrowave"),
    ("synthwave", "80s synth"),
    # K-pop / J-pop
    ("k-pop", "k-pop hits"),
    ("k-pop", "kpop 2024"),
    # Français
    ("french", "chanson française"),
    ("french", "rap français"),
    ("french", "pop française"),
    # Reggae
    ("reggae", "reggae classics"),
    ("reggae", "bob marley"),
    # Blues
    ("blues", "blues classics"),
    ("blues", "delta blues"),
    # Punk
    ("punk", "punk rock"),
    ("punk", "pop punk"),
    # Lo-fi
    ("lofi", "lo-fi hip hop"),
    ("lofi", "lofi beats"),
]


# ---------------------------------------------------------------------------
# Profils d'audio features par genre (plages min, max).
# Calibrés à partir de moyennes empiriques de datasets Spotify publics.
# ---------------------------------------------------------------------------
GENRE_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
    "pop":         {"danceability": (0.55, 0.85), "energy": (0.55, 0.85), "valence": (0.40, 0.85), "tempo": (90, 140), "acousticness": (0.05, 0.45), "instrumentalness": (0.0, 0.05), "speechiness": (0.03, 0.18), "loudness": (-8.0, -3.5)},
    "rock":        {"danceability": (0.35, 0.65), "energy": (0.65, 0.95), "valence": (0.30, 0.70), "tempo": (90, 160), "acousticness": (0.02, 0.30), "instrumentalness": (0.0, 0.10), "speechiness": (0.03, 0.10), "loudness": (-9.0, -3.5)},
    "hip-hop":     {"danceability": (0.65, 0.95), "energy": (0.50, 0.85), "valence": (0.30, 0.75), "tempo": (70, 160), "acousticness": (0.03, 0.30), "instrumentalness": (0.0, 0.02), "speechiness": (0.10, 0.40), "loudness": (-9.0, -3.5)},
    "electronic":  {"danceability": (0.55, 0.85), "energy": (0.65, 0.95), "valence": (0.40, 0.85), "tempo": (110, 160), "acousticness": (0.0, 0.10), "instrumentalness": (0.05, 0.80), "speechiness": (0.03, 0.10), "loudness": (-7.0, -3.0)},
    "indie":       {"danceability": (0.40, 0.75), "energy": (0.35, 0.75), "valence": (0.30, 0.75), "tempo": (80, 140), "acousticness": (0.20, 0.70), "instrumentalness": (0.0, 0.20), "speechiness": (0.03, 0.10), "loudness": (-10.0, -5.0)},
    "metal":       {"danceability": (0.25, 0.55), "energy": (0.85, 1.00), "valence": (0.20, 0.55), "tempo": (90, 200), "acousticness": (0.0, 0.05), "instrumentalness": (0.0, 0.30), "speechiness": (0.04, 0.15), "loudness": (-6.0, -2.0)},
    "classical":   {"danceability": (0.10, 0.40), "energy": (0.05, 0.40), "valence": (0.10, 0.50), "tempo": (50, 130), "acousticness": (0.85, 0.99), "instrumentalness": (0.70, 0.95), "speechiness": (0.03, 0.07), "loudness": (-25.0, -12.0)},
    "jazz":        {"danceability": (0.40, 0.70), "energy": (0.20, 0.55), "valence": (0.40, 0.75), "tempo": (90, 160), "acousticness": (0.55, 0.90), "instrumentalness": (0.30, 0.85), "speechiness": (0.04, 0.10), "loudness": (-15.0, -8.0)},
    "country":     {"danceability": (0.50, 0.75), "energy": (0.50, 0.75), "valence": (0.45, 0.80), "tempo": (90, 140), "acousticness": (0.20, 0.65), "instrumentalness": (0.0, 0.05), "speechiness": (0.03, 0.10), "loudness": (-9.0, -4.0)},
    "r&b":         {"danceability": (0.55, 0.80), "energy": (0.40, 0.70), "valence": (0.30, 0.70), "tempo": (70, 120), "acousticness": (0.10, 0.50), "instrumentalness": (0.0, 0.05), "speechiness": (0.03, 0.15), "loudness": (-10.0, -5.0)},
    "latin":       {"danceability": (0.65, 0.95), "energy": (0.60, 0.90), "valence": (0.55, 0.90), "tempo": (90, 180), "acousticness": (0.05, 0.40), "instrumentalness": (0.0, 0.05), "speechiness": (0.04, 0.20), "loudness": (-7.0, -3.0)},
    "funk":        {"danceability": (0.70, 0.95), "energy": (0.60, 0.90), "valence": (0.65, 0.95), "tempo": (95, 130), "acousticness": (0.05, 0.30), "instrumentalness": (0.0, 0.10), "speechiness": (0.03, 0.10), "loudness": (-8.0, -3.5)},
    "synthwave":   {"danceability": (0.45, 0.75), "energy": (0.55, 0.85), "valence": (0.40, 0.80), "tempo": (90, 130), "acousticness": (0.0, 0.10), "instrumentalness": (0.05, 0.50), "speechiness": (0.03, 0.08), "loudness": (-8.0, -4.0)},
    "k-pop":       {"danceability": (0.60, 0.85), "energy": (0.60, 0.90), "valence": (0.45, 0.85), "tempo": (90, 145), "acousticness": (0.05, 0.30), "instrumentalness": (0.0, 0.05), "speechiness": (0.04, 0.15), "loudness": (-7.0, -3.0)},
    "french":      {"danceability": (0.50, 0.80), "energy": (0.40, 0.80), "valence": (0.35, 0.75), "tempo": (80, 140), "acousticness": (0.15, 0.60), "instrumentalness": (0.0, 0.10), "speechiness": (0.05, 0.30), "loudness": (-9.0, -4.0)},
    "reggae":      {"danceability": (0.65, 0.85), "energy": (0.45, 0.75), "valence": (0.55, 0.85), "tempo": (60, 110), "acousticness": (0.20, 0.55), "instrumentalness": (0.0, 0.10), "speechiness": (0.04, 0.15), "loudness": (-9.0, -5.0)},
    "blues":       {"danceability": (0.45, 0.70), "energy": (0.30, 0.65), "valence": (0.30, 0.70), "tempo": (70, 130), "acousticness": (0.40, 0.85), "instrumentalness": (0.0, 0.30), "speechiness": (0.03, 0.10), "loudness": (-12.0, -6.0)},
    "punk":        {"danceability": (0.40, 0.65), "energy": (0.80, 0.99), "valence": (0.40, 0.80), "tempo": (130, 200), "acousticness": (0.0, 0.10), "instrumentalness": (0.0, 0.05), "speechiness": (0.04, 0.12), "loudness": (-6.0, -2.5)},
    "lofi":        {"danceability": (0.55, 0.80), "energy": (0.20, 0.50), "valence": (0.30, 0.70), "tempo": (60, 95), "acousticness": (0.40, 0.85), "instrumentalness": (0.30, 0.85), "speechiness": (0.03, 0.08), "loudness": (-15.0, -9.0)},
}


def synth_features(genre: str) -> dict:
    """Génère un set d'audio features dans la plage typique du genre."""
    profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["pop"])
    return {f: round(random.uniform(*r), 3) for f, r in profile.items()}


def fetch_query(query: str, retry: int = 0) -> list[dict]:
    """Interroge iTunes ; gère 429 avec backoff."""
    params = urllib.parse.urlencode(
        {"term": query, "entity": "song", "limit": PER_QUERY_LIMIT, "country": "US"}
    )
    url = f"{ITUNES_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "spotifie/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("results", [])
    except urllib.error.HTTPError as e:
        if e.code == 429 and retry < 4:
            wait = 2.0 * (2 ** retry)
            print(f"   ⏳ 429, attente {wait:.0f}s puis retry {retry+1}/4…")
            time.sleep(wait)
            return fetch_query(query, retry + 1)
        print(f"   ! HTTP {e.code} pour « {query} »")
        return []
    except Exception as e:
        print(f"   ! erreur réseau pour « {query} » : {e}")
        return []


def main() -> None:
    init_db()

    if "--reset" in sys.argv:
        execute("DELETE FROM playlist_tracks")
        execute("DELETE FROM user_interactions")
        execute("DELETE FROM tracks")
        print("==> Catalogue réinitialisé.")

    # Évite les doublons grâce à un set de clés (titre+artiste lowercase)
    existing = set()
    for row in (query_one("SELECT id FROM tracks LIMIT 1"),):
        if row:
            from backend.database import query_all
            for r in query_all("SELECT title, artist FROM tracks"):
                existing.add(_key(r["title"], r["artist"]))

    print(f"==> Construction du catalogue depuis iTunes ({len(GENRE_QUERIES)} requêtes)…")
    print(f"    Délai {BASE_DELAY}s entre requêtes — total estimé : ~{len(GENRE_QUERIES)*BASE_DELAY:.0f}s")
    print()

    rows_to_insert: list[tuple] = []
    seen_in_batch = set()

    for q_idx, (genre, query) in enumerate(GENRE_QUERIES, 1):
        print(f"[{q_idx:2d}/{len(GENRE_QUERIES)}] {genre:12s} — « {query} »", end=" ")
        results = fetch_query(query)
        added = 0
        for r in results:
            title = (r.get("trackName") or "").strip()
            artist = (r.get("artistName") or "").strip()
            preview = r.get("previewUrl")
            if not title or not artist or not preview:
                continue

            key = _key(title, artist)
            if key in existing or key in seen_in_batch:
                continue
            seen_in_batch.add(key)

            artwork = (r.get("artworkUrl100") or "").replace("100x100", "600x600")
            duration = r.get("trackTimeMillis")
            album = r.get("collectionName")
            features = synth_features(genre)

            rows_to_insert.append(
                (
                    None,                                      # spotify_id
                    title, artist, album, preview, artwork,
                    duration, random.randint(40, 90),          # popularity
                    genre,
                    features["danceability"], features["energy"], features["valence"], features["tempo"],
                    features["acousticness"], features["instrumentalness"], features["speechiness"], features["loudness"],
                )
            )
            added += 1
        print(f"+ {added} morceaux")
        time.sleep(BASE_DELAY)

    if not rows_to_insert:
        print("==> Aucun nouveau morceau à insérer.")
        return

    sql = """
        INSERT INTO tracks
          (spotify_id, title, artist, album, preview_url, image_url,
           duration_ms, popularity, genre,
           danceability, energy, valence, tempo,
           acousticness, instrumentalness, speechiness, loudness)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    execute_many(sql, rows_to_insert)

    total = query_one("SELECT COUNT(*) AS n FROM tracks")
    print()
    print(f"==> {len(rows_to_insert)} nouveaux morceaux insérés.")
    print(f"==> Catalogue total : {dict(total)['n']} morceaux.")


def _key(title: str, artist: str) -> str:
    return f"{title.lower().strip()}|{artist.lower().strip()}"


if __name__ == "__main__":
    main()
