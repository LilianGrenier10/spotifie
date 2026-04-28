"""
Enrichit le catalogue avec les VRAIES preview_url et image_url depuis
l'API iTunes Search (publique, pas d'auth).

Gère les rate limits (HTTP 429) avec backoff exponentiel :
    - Sleep de base : 0.4s entre chaque requête
    - Si 429 : double le délai et retente jusqu'à 4 fois

Utilisation :
    python3 -m backend.enrich_with_itunes
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import init_db, query_all, execute


ITUNES_URL = "https://itunes.apple.com/search"

BASE_DELAY = 0.4    # secondes entre chaque requête
MAX_RETRIES = 4     # nombre de tentatives en cas de 429


def search_itunes(title: str, artist: str, retry: int = 0, delay: float = 1.0) -> dict | None:
    """Recherche un morceau sur iTunes ; gère 429 avec backoff."""
    term = f"{title} {artist}"
    params = urllib.parse.urlencode(
        {"term": term, "entity": "song", "limit": 5, "country": "US"}
    )
    url = f"{ITUNES_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "spotifie/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429 and retry < MAX_RETRIES:
            sleep_s = delay * (2 ** retry)
            print(f"   ⏳ 429 reçu, attente {sleep_s:.1f}s puis retry {retry+1}/{MAX_RETRIES}…")
            time.sleep(sleep_s)
            return search_itunes(title, artist, retry + 1, delay)
        print(f"   ! HTTP {e.code} pour « {title} »")
        return None
    except Exception as e:
        print(f"   ! erreur réseau pour « {title} » : {e}")
        return None

    results = data.get("results", [])
    if not results:
        return None

    # On préfère un résultat dont le titre matche
    title_lower = title.lower().split("(")[0].strip()
    for r in results:
        if title_lower in (r.get("trackName", "") or "").lower():
            return r
    return results[0]


def main() -> None:
    init_db()
    rows = query_all(
        """SELECT id, title, artist, preview_url, image_url
             FROM tracks
            WHERE preview_url IS NULL OR preview_url = ''
               OR image_url   IS NULL OR image_url   = ''
               OR image_url LIKE '%aaaaa%'        -- placeholders synthétiques
               OR image_url LIKE '%bbbbb%'
               OR image_url LIKE '%ccccc%'
               OR image_url LIKE '%ddddd%'
               OR image_url LIKE '%eeeee%'
               OR image_url LIKE '%fffff%'
               OR image_url LIKE '%11111%'
               OR image_url LIKE '%22222%'
               OR image_url LIKE '%33333%'
               OR image_url LIKE '%44444%'
               OR image_url LIKE '%55555%'
               OR image_url LIKE '%66666%'
               OR image_url LIKE '%77777%'
               OR image_url LIKE '%88888%'
               OR image_url LIKE '%99999%'
               OR image_url LIKE '%abcde%'"""
    )
    if not rows:
        print("==> Aucun morceau à enrichir, tout est déjà à jour.")
        return

    print(f"==> Enrichissement de {len(rows)} morceaux via iTunes Search API…")
    print(f"    (délai {BASE_DELAY}s entre chaque requête, ~{len(rows)*BASE_DELAY:.0f}s au total)")
    print()

    ok = failed = 0
    for i, r in enumerate(rows, 1):
        track = dict(r)
        print(f"[{i:4d}/{len(rows)}] {track['title']} — {track['artist']}", end=" ")
        result = search_itunes(track["title"], track["artist"])

        if not result:
            print("✗ pas de résultat")
            failed += 1
            time.sleep(BASE_DELAY)
            continue

        preview = result.get("previewUrl")
        artwork = (result.get("artworkUrl100") or "").replace("100x100", "600x600")
        if not preview and not artwork:
            print("✗ aucune donnée")
            failed += 1
            time.sleep(BASE_DELAY)
            continue

        execute(
            """UPDATE tracks
                  SET preview_url = COALESCE(?, preview_url),
                      image_url   = COALESCE(?, image_url)
                WHERE id = ?""",
            (preview, artwork or None, track["id"]),
        )
        print("✓")
        ok += 1
        time.sleep(BASE_DELAY)

    print()
    print(f"==> Terminé : {ok} enrichis, {failed} sans résultat.")


if __name__ == "__main__":
    main()
