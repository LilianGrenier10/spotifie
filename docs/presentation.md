# SPOTIFIÉ — Document de présentation

> Document à présenter au jury le **28 avril 2026** (15 min + 5 min Q&R).

---

## 1. Rôles dans le binôme

| Membre        | Périmètre                                                                       |
|---------------|---------------------------------------------------------------------------------|
| **Lilian**    | Backend Flask, modélisation BDD, algo de recommandation, intégration Spotify, OAuth, câblage front/back, documentation. |
| **Co-équipier** | Front-end : maquettes HTML/CSS, design system (thème sombre + accent violet), composants visuels (cards, header). |

---

## 2. Technologies

| Couche              | Choix                            |
|---------------------|----------------------------------|
| Langage backend     | Python 3.10                      |
| Framework HTTP      | Flask 3.0 (Blueprints)           |
| BDD                 | SQLite 3 + driver standard `sqlite3` |
| ORM / requêtes      | SQL brut + helpers maison        |
| Algo                | scikit-learn (cosine similarity) |
| Auth locale         | bcrypt + PyJWT                   |
| Auth Spotify        | spotipy (OAuth Authorization Code) |
| Frontend            | HTML5, CSS3, JavaScript vanille  |
| Audio               | `<audio>` HTML5 + previews 30 s  |
| Icons               | Font Awesome 6                   |
| Police              | Inter (Google Fonts)             |
| Versionning         | Git + GitHub                     |

---

## 3. Architecture en bref

```
   Navigateur (HTML/CSS/JS) ─── REST/JSON ───►  Flask  ───► Spotify API
                                                  │
                                                  ▼
                                              SQLite
                                          (5 tables FK)
```

**Logique métier** isolée dans 3 modules :

* `recommender.py` — algo de recommandation (content-based + exotique).
* `spotify_client.py` — wrapper OAuth + export playlist.
* `auth.py` — hashing bcrypt + JWT + décorateur `@login_required`.

---

## 4. L'algorithme de recommandation (point fort de la soutenance)

### Idée centrale
On représente chaque morceau par un vecteur de 8 dimensions issues des audio
features Spotify : `danceability`, `energy`, `valence`, `acousticness`,
`instrumentalness`, `speechiness`, `tempo` (normalisé), `loudness` (normalisé).

Le **vecteur de goût** d'un utilisateur est la moyenne des morceaux likés,
légèrement éloignée du barycentre des morceaux disliked (anti-likes).

```python
taste = mean(liked) + 0.5 * (mean(liked) - mean(disliked))
sims  = cosine_similarity(taste, candidates)
score = sims + 0.1 * popularity
```

### Originalité : la part d'exotisme

On scinde les candidats en deux pools :

* **In-taste** : morceaux dont le `genre` est dans la liste des genres déjà
  likés.
* **Exotic** : morceaux dont le `genre` n'a jamais été liké.

On retourne `2 in-taste + 1 exotic` (ratio configurable par l'utilisateur via
le slider « Curiosité ») — le morceau exotique est choisi parmi les populaires
pour éviter les recommandations trop hostiles.

### Cold start

Si l'utilisateur vient de s'inscrire (aucun like), on lui sert 3 morceaux
populaires de genres distincts pour amorcer son profil.

---

## 5. Schéma de la base (5 tables)

* `users (id, email, password_hash, display_name, spotify_id, …, exotic_factor)`
* `tracks (id, spotify_id, title, artist, album, audio_features×8, popularity, genre)`
* `playlists (id, user_id, name, description, spotify_playlist_id)`
* `playlist_tracks (playlist_id, track_id, position)` — jointure n-n
* `user_interactions (id, user_id, track_id, action, created_at)` — base de l'algo

Voir `docs/uml.md` pour les diagrammes complets.

---

## 6. Démo prévue (15 min)

| Min   | Étape                                                                              |
|-------|------------------------------------------------------------------------------------|
| 0-2   | Pitch : « SPOTIFIÉ apprend vos goûts et vous fait découvrir 3 morceaux/jour ».     |
| 2-4   | Architecture & technologies (slide / schéma).                                      |
| 4-6   | Démo : création de compte → arrivée sur Découvrir (cold start) → 3 morceaux populaires de genres distincts. |
| 6-9   | Like/dislike de plusieurs morceaux → refresh → on voit les recos s'adapter ; le badge ✨ DÉCOUVERTE apparaît sur le 3ᵉ morceau d'un genre nouveau. |
| 9-11  | Bouger le slider « Curiosité » → impact visible sur la part d'exotisme.            |
| 11-13 | Ajout de 2-3 morceaux à une playlist → renommage → connexion Spotify → export.     |
| 13-15 | Aperçu rapide du code : `recommender.py` (≈ 130 lignes), schéma BDD, blueprints.   |

**Plan B** si pas de Wi-Fi : tout marche en local (catalogue CSV, OAuth
désactivé, lecture audio sur les preview_url qui restent disponibles).

---

## 7. Captures d'écran à inclure

À prendre avant la soutenance :

1. Page d'accueil (hero).
2. Page Découverte avec 3 cartes dont une avec badge ✨ DÉCOUVERTE.
3. Carte en cours de lecture (barre de progression).
4. Modal "Ajouter à une playlist".
5. Page Mes Playlists avec une playlist remplie.
6. Bouton "Connecter Spotify" + redirection.
7. Schéma de l'architecture (depuis `docs/uml.md`).

---

## 8. Questions probables du jury (et réponses préparées)

> *« Pourquoi cosine similarity et pas une distance euclidienne ? »*
La cosine similarity ignore l'amplitude du vecteur et ne mesure que l'angle :
deux morceaux peuvent avoir des features très différentes en valeur absolue
(par ex. l'un est plus fort en `loudness`) mais avoir le même *profil*.
C'est ce qu'on veut capturer.

> *« Comment gérez-vous la cold start ? »*
On retourne 3 morceaux populaires de genres distincts. Dès le premier like,
le vecteur de goût existe et l'algo bascule sur le filtrage par contenu.

> *« Pourquoi 5 tables ? »*
Le minimum demandé est 3, on en a 5 pour pouvoir représenter une jointure
n-n entre playlists et tracks (avec un `position`) sans dénormaliser, et
pour stocker l'historique d'interactions séparément (utile pour l'algo).

> *« Pourquoi avoir choisi SQLite ? »*
Zéro configuration, fichier unique, parfait pour la démo et les tests
automatisés. Pour la production, on migrerait sur PostgreSQL avec
SQLAlchemy en deux soirées.

> *« Comment fonctionne l'OAuth Spotify ? »*
Authorization Code Flow : on redirige l'utilisateur vers Spotify, il accepte
les scopes (`playlist-modify-public`, etc.), Spotify nous renvoie un `code` à
notre callback, on l'échange contre un `access_token` + `refresh_token`. Le
refresh est automatique via spotipy si l'access expire.

> *« Avez-vous géré les erreurs réseau / les rate limits Spotify ? »*
On gère le refresh automatique du token et on batch les requêtes d'export
par 100 (limite Spotify). Pour les rate limits, en cas d'échec, l'erreur est
remontée à l'utilisateur via un toast (pas de retry automatique pour cette
version).
