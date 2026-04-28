# Diagrammes UML — SPOTIFIÉ

Ce document contient les diagrammes UML demandés (4 pts du barème : « Traduire
un besoin fonctionnel en modèle de données »). Tous les diagrammes sont en
[Mermaid](https://mermaid.js.org/) — visualisables sur GitHub, dans VS Code
avec l'extension Mermaid, ou sur https://mermaid.live.

---

## 1. Diagramme de cas d'utilisation

```mermaid
%%{init: {'theme':'dark'}}%%
graph LR
    U([Utilisateur])
    SPOT([API Spotify])

    subgraph SPOTIFIÉ
        UC1((S'inscrire / Se connecter))
        UC2((Découvrir 3 morceaux))
        UC3((Liker / Disliker))
        UC4((Lire un extrait 30s))
        UC5((Créer / éditer playlist))
        UC6((Connecter compte Spotify))
        UC7((Exporter playlist))
        UC8((Régler curiosité))
    end

    U --> UC1
    U --> UC2
    U --> UC3
    U --> UC4
    U --> UC5
    U --> UC8
    U --> UC6 -.OAuth.-> SPOT
    U --> UC7 -.write playlist.-> SPOT
    UC2 -.audio features.-> SPOT
```

---

## 2. Diagramme de classes (POO backend)

```mermaid
%%{init: {'theme':'dark'}}%%
classDiagram
    class Config {
        +SPOTIFY_CLIENT_ID: str
        +SPOTIFY_CLIENT_SECRET: str
        +JWT_SECRET: str
        +DB_PATH: Path
        +spotify_configured() bool
    }

    class Database {
        +init_db() void
        +get_conn() Connection
        +query_one(sql, params) Row
        +query_all(sql, params) list~Row~
        +execute(sql, params) int
    }

    class Auth {
        +hash_password(plain) str
        +verify_password(plain, hash) bool
        +make_token(user_id) str
        +decode_token(token) dict
        +current_user() User
        +login_required(fn) Callable
    }

    class SpotifyClient {
        +authorize_url(state) str
        +exchange_code(code) dict
        +client_for_user(user) Spotify
        -_refresh_if_needed(user) str
        +export_playlist_to_spotify(user, pl, uris) str
    }

    class Recommender {
        -FEATURES: tuple
        -_track_vector(track) ndarray
        -_build_taste_vector(user_id) tuple
        -_cold_start(n) list~Track~
        +recommend(user_id, n) list~Track~
        +explain(user_id) dict
    }

    class FlaskApp {
        +create_app() Flask
        +register_blueprint(bp) void
    }

    class Blueprint {
        <<abstract>>
    }

    class AuthRoutes
    class TracksRoutes
    class PlaylistsRoutes
    class RecommendationsRoutes
    class CatalogRoutes

    AuthRoutes --|> Blueprint
    TracksRoutes --|> Blueprint
    PlaylistsRoutes --|> Blueprint
    RecommendationsRoutes --|> Blueprint
    CatalogRoutes --|> Blueprint

    FlaskApp *-- AuthRoutes
    FlaskApp *-- TracksRoutes
    FlaskApp *-- PlaylistsRoutes
    FlaskApp *-- RecommendationsRoutes
    FlaskApp *-- CatalogRoutes

    AuthRoutes ..> Auth
    AuthRoutes ..> SpotifyClient
    PlaylistsRoutes ..> SpotifyClient
    RecommendationsRoutes ..> Recommender

    Auth ..> Database
    SpotifyClient ..> Database
    Recommender ..> Database

    Database ..> Config
    SpotifyClient ..> Config
    Auth ..> Config
```

---

## 3. Modèle relationnel (5 tables)

```mermaid
erDiagram
    USERS ||--o{ PLAYLISTS : "crée"
    USERS ||--o{ USER_INTERACTIONS : "génère"
    TRACKS ||--o{ PLAYLIST_TRACKS : "appartient à"
    TRACKS ||--o{ USER_INTERACTIONS : "concerne"
    PLAYLISTS ||--o{ PLAYLIST_TRACKS : "contient"

    USERS {
        INTEGER id PK
        TEXT email UNIQUE
        TEXT password_hash
        TEXT display_name
        TEXT spotify_id
        TEXT spotify_access_token
        TEXT spotify_refresh_token
        INTEGER spotify_token_expires_at
        REAL exotic_factor
        TIMESTAMP created_at
    }

    TRACKS {
        INTEGER id PK
        TEXT spotify_id UNIQUE
        TEXT title
        TEXT artist
        TEXT album
        TEXT preview_url
        TEXT image_url
        INTEGER duration_ms
        INTEGER popularity
        TEXT genre
        REAL danceability
        REAL energy
        REAL valence
        REAL tempo
        REAL acousticness
        REAL instrumentalness
        REAL speechiness
        REAL loudness
    }

    PLAYLISTS {
        INTEGER id PK
        INTEGER user_id FK
        TEXT name
        TEXT description
        TEXT cover_url
        TEXT spotify_playlist_id
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    PLAYLIST_TRACKS {
        INTEGER id PK
        INTEGER playlist_id FK
        INTEGER track_id FK
        INTEGER position
        TIMESTAMP added_at
    }

    USER_INTERACTIONS {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER track_id FK
        TEXT action
        TIMESTAMP created_at
    }
```

---

## 4. Diagramme de séquence — recommandation

```mermaid
%%{init: {'theme':'dark'}}%%
sequenceDiagram
    actor U as Utilisateur
    participant F as Front (main.html)
    participant A as Flask /api/recommendations
    participant R as Recommender
    participant DB as SQLite

    U->>F: Ouvre la page Découvrir
    F->>A: GET /api/recommendations (cookie JWT)
    A->>A: login_required → décode JWT
    A->>R: recommend(user_id, n=3)
    R->>DB: SELECT user_interactions (likes / dislikes)
    R->>R: Construit taste_vector
    R->>DB: SELECT tracks WHERE id NOT IN seen
    R->>R: cosine_similarity(taste, candidates)
    R->>R: Sépare in-taste / exotic
    R->>R: Sélectionne 2 in-taste + 1 exotic
    R-->>A: 3 tracks + similarity
    A-->>F: JSON {recommendations: [...]}
    F->>F: Affiche 3 cartes (avec badge ✨ si exotic)

    U->>F: Like sur 1 carte
    F->>A: POST /api/tracks/{id}/interact
    A->>DB: INSERT user_interactions
    A-->>F: 200 OK
    F->>A: GET /api/recommendations (refresh)
    Note over R,DB: Le taste_vector a évolué !
```

---

## 5. Diagramme de séquence — export playlist Spotify

```mermaid
%%{init: {'theme':'dark'}}%%
sequenceDiagram
    actor U as Utilisateur
    participant F as Front (profil.html)
    participant A as Flask /api/playlists/{id}/export
    participant SC as SpotifyClient
    participant SP as API Spotify
    participant DB as SQLite

    U->>F: Clic "Exporter"
    F->>A: POST /api/playlists/{id}/export
    A->>DB: SELECT playlist + tracks (avec spotify_id)
    A->>SC: export_playlist_to_spotify(user, playlist, uris)
    SC->>SC: _refresh_if_needed (rafraîchit access_token si expiré)
    SC->>SP: POST users/{id}/playlists (création)
    SP-->>SC: playlist Spotify créée
    SC->>SP: POST playlists/{id}/tracks (par batch de 100)
    SP-->>SC: OK
    SC->>DB: UPDATE playlists SET spotify_playlist_id = ?
    SC-->>A: external_url
    A-->>F: {ok: true, spotify_url: "https://..."}
    F->>U: Toast "Exportée !" + ouverture nouvel onglet
```
