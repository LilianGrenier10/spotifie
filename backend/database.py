"""
Couche d'accès SQLite.

Schéma relationnel (5 tables) :
    users               - comptes locaux + tokens Spotify
    tracks              - catalogue musical avec audio features
    playlists           - playlists créées par les utilisateurs
    playlist_tracks     - table de jointure (n-n) playlists <-> tracks
    user_interactions   - historique like/dislike/play (matière première de l'algo)
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .config import config


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    email                       TEXT UNIQUE NOT NULL,
    password_hash               TEXT NOT NULL,
    display_name                TEXT,
    spotify_id                  TEXT,
    spotify_access_token        TEXT,
    spotify_refresh_token       TEXT,
    spotify_token_expires_at    INTEGER,
    exotic_factor               REAL DEFAULT 0.25,  -- 0 = uniquement style connu, 1 = full découverte
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id          TEXT UNIQUE,
    title               TEXT NOT NULL,
    artist              TEXT NOT NULL,
    album               TEXT,
    preview_url         TEXT,
    image_url           TEXT,
    duration_ms         INTEGER,
    popularity          INTEGER DEFAULT 50,
    genre               TEXT,
    -- Audio features (Spotify)
    danceability        REAL,
    energy              REAL,
    valence             REAL,
    tempo               REAL,
    acousticness        REAL,
    instrumentalness    REAL,
    speechiness         REAL,
    loudness            REAL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
CREATE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks(spotify_id);

CREATE TABLE IF NOT EXISTS playlists (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,
    name                    TEXT NOT NULL,
    description             TEXT,
    cover_url               TEXT,
    spotify_playlist_id     TEXT,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id     INTEGER NOT NULL,
    track_id        INTEGER NOT NULL,
    position        INTEGER DEFAULT 0,
    added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    UNIQUE (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id);

CREATE TABLE IF NOT EXISTS user_interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    track_id    INTEGER NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('like', 'dislike', 'play', 'skip')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_user_action ON user_interactions(user_id, action);
"""


def init_db() -> None:
    """Crée la base si elle n'existe pas et applique le schéma."""
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Context manager qui ouvre/ferme la connexion SQLite proprement."""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone()


def query_all(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple = ()) -> int:
    """Exécute un INSERT/UPDATE/DELETE et retourne lastrowid."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def execute_many(sql: str, params_list: List[tuple]) -> None:
    with get_conn() as conn:
        conn.executemany(sql, params_list)
        conn.commit()


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row else None


def rows_to_dicts(rows: List[sqlite3.Row]) -> List[dict]:
    return [dict(r) for r in rows]
