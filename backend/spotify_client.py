"""
Wrapper Spotipy : OAuth, recherche, audio features, export playlist.

Les méthodes ici manipulent directement les tokens stockés en BDD.
Tout le code Spotify se concentre dans ce module : si Spotify change son
API, on ne touche qu'à un seul endroit.
"""
from __future__ import annotations

import time
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import config
from .database import execute, query_one


def _oauth_manager(state: Optional[str] = None) -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=config.SPOTIFY_SCOPE,
        state=state,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler(),
        show_dialog=True,
    )


def authorize_url(state: str) -> str:
    """URL vers laquelle rediriger l'utilisateur pour qu'il accepte."""
    return _oauth_manager(state=state).get_authorize_url()


def exchange_code(code: str) -> dict:
    """Échange le code OAuth contre un access_token + refresh_token."""
    return _oauth_manager().get_access_token(code, as_dict=True, check_cache=False)


def save_tokens_to_user(user_id: int, token_info: dict, spotify_id: str) -> None:
    execute(
        """UPDATE users
              SET spotify_id = ?,
                  spotify_access_token = ?,
                  spotify_refresh_token = ?,
                  spotify_token_expires_at = ?
            WHERE id = ?""",
        (
            spotify_id,
            token_info["access_token"],
            token_info["refresh_token"],
            int(token_info["expires_at"]),
            user_id,
        ),
    )


def _refresh_if_needed(user: dict) -> str:
    """Renvoie un access_token valide, le rafraîchit si expiré."""
    if not user.get("spotify_refresh_token"):
        raise RuntimeError("Utilisateur non connecté à Spotify")

    expires_at = user.get("spotify_token_expires_at") or 0
    if expires_at - 60 > time.time():
        return user["spotify_access_token"]

    # Refresh
    oauth = _oauth_manager()
    new_info = oauth.refresh_access_token(user["spotify_refresh_token"])
    execute(
        """UPDATE users
              SET spotify_access_token = ?,
                  spotify_token_expires_at = ?,
                  spotify_refresh_token = COALESCE(?, spotify_refresh_token)
            WHERE id = ?""",
        (
            new_info["access_token"],
            int(new_info["expires_at"]),
            new_info.get("refresh_token"),
            user["id"],
        ),
    )
    return new_info["access_token"]


def client_for_user(user: dict) -> spotipy.Spotify:
    """Spotipy authentifié comme l'utilisateur."""
    token = _refresh_if_needed(user)
    return spotipy.Spotify(auth=token)


def get_me(access_token: str) -> dict:
    return spotipy.Spotify(auth=access_token).current_user()


# ---------------------------------------------------------------------------
# Recherche d'un track sur Spotify par titre + artiste
# ---------------------------------------------------------------------------
def search_track_uri(sp: spotipy.Spotify, title: str, artist: str) -> Optional[str]:
    """Renvoie l'URI Spotify du meilleur match pour (title, artist), ou None."""
    # Requête en deux temps : d'abord avec les filtres précis,
    # sinon en fallback recherche libre (au cas où l'API n'aime pas track:/artist:)
    queries = [
        f'track:"{title}" artist:"{artist}"',
        f"{title} {artist}",
    ]
    for q in queries:
        try:
            res = sp.search(q=q, type="track", limit=5)
        except Exception:
            continue
        items = (res.get("tracks") or {}).get("items") or []
        if not items:
            continue
        # Préférer un résultat dont le titre matche bien
        title_lower = title.lower().split("(")[0].strip()
        for it in items:
            if title_lower in (it.get("name") or "").lower():
                return it["uri"]
        return items[0]["uri"]
    return None


# ---------------------------------------------------------------------------
# Export d'une playlist locale vers le compte Spotify de l'utilisateur
# ---------------------------------------------------------------------------
def export_playlist_to_spotify(user: dict, playlist: dict, tracks: list) -> dict:
    """
    Crée la playlist sur Spotify et y ajoute les morceaux.

    `tracks` est une liste de dicts {spotify_id, title, artist}. Si
    spotify_id est présent on l'utilise directement, sinon on cherche
    le morceau dans le catalogue Spotify par titre + artiste.

    Retourne un dict { url, matched, missing }.
    """
    sp = client_for_user(user)
    me = sp.current_user()

    # 1. Résoudre les URIs Spotify
    uris: list[str] = []
    missing: list[str] = []
    for t in tracks:
        if t.get("spotify_id"):
            uris.append(f"spotify:track:{t['spotify_id']}")
            continue
        uri = search_track_uri(sp, t.get("title") or "", t.get("artist") or "")
        if uri:
            uris.append(uri)
        else:
            missing.append(f'{t.get("title", "?")} — {t.get("artist", "?")}')

    if not uris:
        raise RuntimeError(
            "Aucun morceau de la playlist n'a pu être retrouvé sur Spotify."
        )

    # 2. Créer la playlist Spotify
    sp_playlist = sp.user_playlist_create(
        user=me["id"],
        name=playlist["name"],
        public=False,
        description=playlist.get("description") or "Créée depuis SPOTIFIÉ",
    )

    # 3. Ajouter les morceaux par batch de 100
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(sp_playlist["id"], uris[i : i + 100])

    # 4. Mémoriser l'ID Spotify côté BDD
    execute(
        "UPDATE playlists SET spotify_playlist_id = ? WHERE id = ?",
        (sp_playlist["id"], playlist["id"]),
    )

    return {
        "url": sp_playlist["external_urls"]["spotify"],
        "matched": len(uris),
        "missing": missing,
    }
