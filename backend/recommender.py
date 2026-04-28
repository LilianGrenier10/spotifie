"""
Algorithme de recommandation hybride (content-based + découverte exotique).

Approche :
    1. On construit un "taste vector" : moyenne pondérée des audio features
       des morceaux likés, pénalisée par les disliked.
    2. On calcule la similarité cosinus entre ce vecteur et tous les
       morceaux du catalogue non encore vus.
    3. On retourne 3 morceaux :
        - 2 "in-taste" : les + similaires
        - 1 "exotic"   : un morceau de qualité (popularité élevée) mais
                         d'un genre que l'utilisateur n'a jamais exploré,
                         avec une distance cosinus modérée à élevée.

Cold start : si l'utilisateur n'a aucun like, on retourne 3 morceaux
populaires de genres variés.

Le poids de l'exotisme est paramétrable via users.exotic_factor (0..1).
"""
from __future__ import annotations

import random
from typing import List, Optional, Set, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .database import query_all, query_one, rows_to_dicts


# Ordre fixe des features pour la cohérence des vecteurs
FEATURES = (
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "speechiness",
    "tempo",
    "loudness",
)

# Plages pour normaliser tempo et loudness (les autres sont déjà entre 0 et 1)
_NORM_RANGES = {
    "tempo": (50.0, 220.0),
    "loudness": (-30.0, 0.0),
}


def _normalize(value: Optional[float], feature: str) -> float:
    if value is None:
        return 0.5
    if feature in _NORM_RANGES:
        lo, hi = _NORM_RANGES[feature]
        if hi == lo:
            return 0.5
        return max(0.0, min(1.0, (value - lo) / (hi - lo)))
    return max(0.0, min(1.0, float(value)))


def _track_vector(track: dict) -> np.ndarray:
    return np.array([_normalize(track.get(f), f) for f in FEATURES], dtype=float)


def _build_taste_vector(user_id: int) -> Tuple[Optional[np.ndarray], Set[str]]:
    """Renvoie (vecteur de goût, set des genres aimés) ou (None, set vide)."""
    rows = query_all(
        """SELECT t.*, ui.action
             FROM user_interactions ui
             JOIN tracks t ON t.id = ui.track_id
            WHERE ui.user_id = ?
              AND ui.action IN ('like', 'dislike')""",
        (user_id,),
    )
    if not rows:
        return None, set()

    liked_vecs, disliked_vecs, liked_genres = [], [], set()
    for r in rows:
        t = dict(r)
        v = _track_vector(t)
        if t["action"] == "like":
            liked_vecs.append(v)
            if t.get("genre"):
                liked_genres.add(t["genre"])
        else:
            disliked_vecs.append(v)

    if not liked_vecs:
        return None, set()

    taste = np.mean(liked_vecs, axis=0)
    if disliked_vecs:
        # On éloigne le vecteur des morceaux rejetés (moitié du poids)
        anti = np.mean(disliked_vecs, axis=0)
        taste = taste + 0.5 * (taste - anti)
        taste = np.clip(taste, 0.0, 1.0)

    return taste, liked_genres


def _seen_track_ids(user_id: int) -> set[int]:
    rows = query_all(
        "SELECT DISTINCT track_id FROM user_interactions WHERE user_id = ?",
        (user_id,),
    )
    return {r["track_id"] for r in rows}


def _candidate_tracks(exclude_ids: set[int]) -> list[dict]:
    rows = query_all("SELECT * FROM tracks")
    return [dict(r) for r in rows if r["id"] not in exclude_ids]


def _cold_start(n: int = 3) -> list[dict]:
    """Démarrage à froid : 3 morceaux populaires de genres distincts."""
    rows = query_all(
        "SELECT * FROM tracks ORDER BY popularity DESC LIMIT 80"
    )
    pool = rows_to_dicts(rows)
    seen_genres: set[str] = set()
    picks: list[dict] = []
    random.shuffle(pool)
    for t in pool:
        g = t.get("genre") or "unknown"
        if g in seen_genres:
            continue
        picks.append(t)
        seen_genres.add(g)
        if len(picks) >= n:
            break
    # Si pas assez de genres distincts, on complète
    while len(picks) < n and pool:
        candidate = pool.pop()
        if candidate not in picks:
            picks.append(candidate)
    return picks[:n]


def recommend(user_id: int, n: int = 3) -> list[dict]:
    """Renvoie n recommandations pour l'utilisateur."""
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        return []

    exotic_factor = float(dict(user).get("exotic_factor") or 0.25)
    seen = _seen_track_ids(user_id)
    candidates = _candidate_tracks(seen)
    if not candidates:
        # L'utilisateur a tout vu, on ré-injecte les liked en mode shuffle
        return _cold_start(n)

    taste, liked_genres = _build_taste_vector(user_id)
    if taste is None:
        return _cold_start(n)

    # Matrice candidats
    matrix = np.vstack([_track_vector(t) for t in candidates])
    sims = cosine_similarity(taste.reshape(1, -1), matrix)[0]

    # Score = similarité + bonus popularité léger
    pop = np.array([(t.get("popularity") or 50) / 100.0 for t in candidates])
    in_taste_score = sims + 0.1 * pop

    # Indices triés par score décroissant
    sorted_idx = np.argsort(-in_taste_score)

    # On sépare in-taste (genres connus) et exotic (genres inconnus)
    in_taste_picks: list[dict] = []
    exotic_pool: list[tuple[int, dict]] = []
    for idx in sorted_idx:
        t = candidates[idx]
        if t.get("genre") and t["genre"] not in liked_genres:
            exotic_pool.append((idx, t))
        else:
            in_taste_picks.append(t)

    # Combien d'exotiques ? Au moins 1 si possible.
    n_exotic = max(1, round(n * exotic_factor)) if exotic_pool else 0
    n_in_taste = n - n_exotic

    final = in_taste_picks[:n_in_taste]

    if n_exotic and exotic_pool:
        # Pour la suggestion exotique, on choisit parmi les morceaux populaires
        # ET pas trop éloignés du goût (pour éviter le total désastre).
        exotic_pool.sort(
            key=lambda x: -((x[1].get("popularity") or 50) / 100.0 + 0.5 * sims[x[0]])
        )
        for _, t in exotic_pool[:n_exotic]:
            final.append(t)

    # Au cas où on n'aurait pas atteint n, on complète avec in-taste
    while len(final) < n and in_taste_picks:
        nxt = in_taste_picks[len(final)] if len(final) < len(in_taste_picks) else None
        if not nxt or nxt in final:
            break
        final.append(nxt)

    # On enrichit chaque reco avec un flag "is_exotic" et le score
    out = []
    for t in final[:n]:
        idx = candidates.index(t)
        out.append(
            {
                **t,
                "is_exotic": t.get("genre") not in liked_genres,
                "similarity": round(float(sims[idx]), 3),
            }
        )
    return out


def explain(user_id: int) -> dict:
    """Renvoie un résumé des goûts pour l'UI / debug."""
    taste, liked_genres = _build_taste_vector(user_id)
    likes = query_one(
        "SELECT COUNT(*) AS n FROM user_interactions WHERE user_id=? AND action='like'",
        (user_id,),
    )
    dislikes = query_one(
        "SELECT COUNT(*) AS n FROM user_interactions WHERE user_id=? AND action='dislike'",
        (user_id,),
    )
    return {
        "likes": dict(likes)["n"] if likes else 0,
        "dislikes": dict(dislikes)["n"] if dislikes else 0,
        "taste_vector": (
            {f: round(float(v), 3) for f, v in zip(FEATURES, taste.tolist())}
            if taste is not None
            else None
        ),
        "liked_genres": sorted(liked_genres),
    }
