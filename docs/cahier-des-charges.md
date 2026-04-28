# Cahier des charges — SPOTIFIÉ

**Projet Fil Rouge B2 Ynov Lille — Promotion INFO B2**
**Sujet : Projet 4 — Système de Recommandation Musicale (28 pts)**
**Auteur : Lilian (lili10122006@gmail.com)**

---

## 1. Présentation du projet

SPOTIFIÉ est une application web qui apprend les goûts musicaux de l'utilisateur
au fil de ses interactions (likes / dislikes) puis lui propose, à chaque session,
**3 recommandations personnalisées** : deux morceaux dans la veine de ses goûts,
et **une découverte exotique** d'un genre non exploré, pour élargir son univers
musical.

L'application s'appuie sur l'**API Spotify** pour la lecture des extraits 30
secondes, l'authentification OAuth, et l'export des playlists créées vers le
compte Spotify de l'utilisateur.

### 1.1 Objectifs

* Démontrer la maîtrise de la **POO** côté backend (modules métier, séparation
  des responsabilités, classes Config).
* Construire une **architecture client / serveur** propre (REST API JSON +
  front-end statique) — communication entre 2 logiciels (6 pts).
* Concevoir un **modèle relationnel** cohérent à 5 tables avec contraintes,
  index et clés étrangères (3 pts).
* Implémenter un **algorithme de recommandation** non trivial (filtrage par
  contenu + injection de découverte) en s'appuyant sur scikit-learn (5 pts).
* Couvrir un **CRUD complet** sur les playlists (4 pts).
* Permettre l'**import CSV** d'un catalogue musical (2 pts).
* Soigner l'**interaction utilisateur** (clics, slider, drag visuel) (2 pts).

### 1.2 Cible utilisateur

Tout utilisateur souhaitant découvrir de nouvelles musiques sans dépendre des
recommandations opaques d'une plateforme commerciale, tout en gardant ses
playlists synchronisées avec son compte Spotify.

---

## 2. Spécifications fonctionnelles

### 2.1 Parcours utilisateur principal

| Étape                    | Page              | Action                                                                                         |
|--------------------------|-------------------|------------------------------------------------------------------------------------------------|
| 1. Arrivée               | `/index.html`     | Page d'accueil, découverte du concept, CTA « Démarrer ».                                       |
| 2. Inscription           | `/register.html`  | Création du compte local (email + mdp + pseudo).                                                |
| 3. Connexion             | `/login.html`     | Si compte déjà existant.                                                                       |
| 4. Découverte            | `/main.html`      | Affichage de 3 morceaux + lecture 30 s + like/dislike + ajout à playlist.                       |
| 5. Réglage de curiosité  | `/main.html`      | Slider « Curiosité » qui pondère la part de recommandations exotiques (0 % → 100 %).            |
| 6. Mes playlists         | `/profil.html`    | CRUD complet : créer, renommer, supprimer, ajouter/retirer des morceaux.                       |
| 7. Connexion Spotify     | `/profil.html`    | OAuth Spotify pour récupérer un access_token.                                                  |
| 8. Export Spotify        | `/profil.html`    | Bouton « Exporter » qui crée la playlist dans le compte Spotify de l'utilisateur.              |

### 2.2 Cas d'usage détaillés

**UC-1 : Recevoir des recommandations personnalisées**
* **Acteur** : Utilisateur connecté.
* **Préconditions** : Catalogue importé en BDD.
* **Scénario nominal** :
  1. L'utilisateur ouvre `/main.html`.
  2. Le serveur calcule un *taste vector* à partir de ses likes/dislikes.
  3. Le serveur retourne 3 morceaux : 2 in-taste + 1 exotique.
  4. L'utilisateur écoute, like ou dislike.
* **Scénario de démarrage à froid** : si aucun like, on retourne 3 morceaux
  populaires de genres différents pour amorcer le profil.

**UC-2 : Créer une playlist et l'exporter sur Spotify**
* **Préconditions** : Utilisateur connecté et compte Spotify lié.
* **Scénario nominal** :
  1. Création de la playlist via `POST /api/playlists`.
  2. Ajout de morceaux via `POST /api/playlists/<id>/tracks`.
  3. Clic sur « Exporter » → `POST /api/playlists/<id>/export`.
  4. Le serveur crée la playlist Spotify et y ajoute les morceaux par batch
     de 100 (limite Spotify).
  5. Le serveur retourne l'URL Spotify, qui s'ouvre dans un nouvel onglet.

**UC-3 : Import du catalogue (admin / dev)**
* `POST /api/catalog/import` accepte un CSV (form-data ou raw text) au
  format documenté dans `routes/catalog_routes.py`. Idempotent (`INSERT OR
  REPLACE` sur `spotify_id`).

### 2.3 Règles métier

* Un utilisateur ne peut pas dupliquer un morceau dans une même playlist
  (contrainte UNIQUE sur `(playlist_id, track_id)`).
* Une suppression de playlist supprime ses associations en cascade
  (`ON DELETE CASCADE`).
* Le facteur d'exotisme est borné à `[0.0, 1.0]`.
* L'`access_token` Spotify est rafraîchi automatiquement quand il expire (60 s
  de marge).

---

## 3. Spécifications techniques

### 3.1 Stack

| Couche              | Choix                            | Justification                                              |
|---------------------|----------------------------------|------------------------------------------------------------|
| Backend             | Python 3.10 + Flask 3            | Léger, rapide à mettre en place, ecosystem ML mature.       |
| BDD                 | SQLite                           | Zéro config, fichier unique, parfait pour la démo.         |
| Algo                | scikit-learn (cosine similarity) | Classique et performant pour content-based filtering.       |
| Auth locale         | bcrypt + JWT (PyJWT)             | Standard sécurisé.                                          |
| Auth Spotify        | spotipy (Authorization Code)     | Wrapper officiel de l'API Spotify.                          |
| Front               | HTML / CSS / JS vanille          | Aucune dépendance build, démo facile.                       |
| Audio               | `<audio>` HTML5 + preview 30s    | Marche sans Premium ; avec Premium possible via SDK Web.    |
| Communication       | REST JSON over HTTP              | Standard, debuggable.                                       |

### 3.2 Architecture

```
┌──────────────┐                ┌──────────────────┐
│  Front-end   │                │   API Spotify    │
│  HTML/CSS/JS │ ◄────────────► │  (api.spotify.com)│
└──────┬───────┘                └────────▲─────────┘
       │ JSON / Cookie JWT               │
       ▼                                  │ OAuth + REST
┌──────────────────────────────┐          │
│       Backend Flask          │──────────┘
│  ┌────────────────────────┐  │
│  │  Routes (Blueprint)    │  │
│  │  - /api/auth           │  │
│  │  - /api/tracks         │  │
│  │  - /api/playlists      │  │
│  │  - /api/recommendations│  │
│  │  - /api/catalog        │  │
│  └────────────┬───────────┘  │
│  ┌────────────┴───────────┐  │
│  │  Logique métier        │  │
│  │  - recommender.py      │  │
│  │  - spotify_client.py   │  │
│  │  - auth.py             │  │
│  └────────────┬───────────┘  │
│  ┌────────────┴───────────┐  │
│  │  database.py (SQLite)  │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
```

### 3.3 Algorithme de recommandation

Le module `backend/recommender.py` implémente un **filtrage par contenu** sur 8
audio features de Spotify : `danceability`, `energy`, `valence`, `acousticness`,
`instrumentalness`, `speechiness`, `tempo` (normalisé), `loudness` (normalisé).

**Étapes** :
1. **Construction du vecteur de goût** : moyenne des features des morceaux
   likés, ajustée par soustraction (50 %) du barycentre des dislikes.
2. **Calcul des similarités** : `sklearn.metrics.pairwise.cosine_similarity`
   entre le vecteur de goût et chaque candidat (morceaux non vus).
3. **Score** : `similarité + 0.1 × popularité_normalisée`.
4. **Sélection finale** :
    * 2 morceaux les plus similaires *parmi les genres déjà likés* (in-taste).
    * 1 morceau *parmi les genres jamais explorés* (exotique), choisi pour sa
      popularité et une similarité résiduelle non nulle (éviter les chocs trop
      brutaux).
5. **Cold start** : si l'utilisateur n'a aucun like, retour de 3 morceaux
   populaires de genres distincts.

Le ratio in-taste / exotique est paramétrable par utilisateur via le slider
« Curiosité » (`users.exotic_factor` en BDD, 0.0 → 1.0).

### 3.4 Sécurité

* Mots de passe stockés en bcrypt (salt automatique).
* JWT signé HS256, durée 7 jours, transporté en cookie HttpOnly.
* Tokens Spotify chiffrés en BDD (à minima : access + refresh stockés en clair
  pour la démo, à passer en chiffrement applicatif en production).
* CORS activé seulement si l'origine est autorisée (Flask-CORS).
* Toutes les routes protégées passent par le décorateur `@login_required`.

---

## 4. Modèle de données (5 tables)

Voir `docs/uml.md` pour le diagramme. Résumé :

| Table              | Rôle                                                    | Cardinalités                       |
|--------------------|---------------------------------------------------------|------------------------------------|
| `users`            | Compte local + tokens Spotify + préférences             | 1 → N `playlists`, 1 → N `interactions` |
| `tracks`           | Catalogue avec audio features                           | N → N `playlists` via jointure     |
| `playlists`        | Playlists créées par l'utilisateur                      | N → 1 `users`                      |
| `playlist_tracks`  | Jointure n-n + position                                 | UNIQUE (playlist_id, track_id)     |
| `user_interactions`| Historique like/dislike/play/skip — base de l'algo      | N → 1 `users`, N → 1 `tracks`      |

---

## 5. Endpoints API

| Méthode | Endpoint                                     | Auth | Rôle                                  |
|---------|----------------------------------------------|------|---------------------------------------|
| POST    | `/api/auth/register`                         | -    | Création de compte                    |
| POST    | `/api/auth/login`                            | -    | Connexion                             |
| POST    | `/api/auth/logout`                           | -    | Déconnexion                           |
| GET     | `/api/auth/me`                               | ✓    | Profil courant                        |
| POST    | `/api/auth/preferences`                      | ✓    | Mise à jour exotic_factor             |
| GET     | `/api/auth/spotify/login`                    | ✓    | Redirection vers OAuth Spotify        |
| GET     | `/api/auth/spotify/callback`                 | -    | Callback OAuth                        |
| POST    | `/api/auth/spotify/disconnect`               | ✓    | Déconnecte Spotify                    |
| GET     | `/api/tracks`                                | -    | Liste / recherche du catalogue        |
| GET     | `/api/tracks/<id>`                           | -    | Détail d'un morceau                   |
| POST    | `/api/tracks/<id>/interact`                  | ✓    | Enregistre like/dislike/play/skip     |
| GET     | `/api/tracks/genres`                         | -    | Histogramme des genres                |
| GET     | `/api/recommendations`                       | ✓    | 3 recommandations                     |
| GET     | `/api/recommendations/explain`               | ✓    | Vecteur de goût pour debug            |
| GET     | `/api/playlists`                             | ✓    | Liste des playlists                   |
| POST    | `/api/playlists`                             | ✓    | **C** : créer                         |
| GET     | `/api/playlists/<id>`                        | ✓    | **R** : lire                          |
| PUT     | `/api/playlists/<id>`                        | ✓    | **U** : mettre à jour                 |
| DELETE  | `/api/playlists/<id>`                        | ✓    | **D** : supprimer                     |
| POST    | `/api/playlists/<id>/tracks`                 | ✓    | Ajout d'un morceau                    |
| DELETE  | `/api/playlists/<id>/tracks/<track_id>`      | ✓    | Retrait d'un morceau                  |
| POST    | `/api/playlists/<id>/export`                 | ✓    | Export vers Spotify                   |
| POST    | `/api/catalog/import`                        | -    | Import CSV du catalogue               |
| GET     | `/api/health`                                | -    | Health check                          |

---

## 6. Mapping avec le barème

| Item du barème                                  | Pts | Réalisé par                                                                                    |
|-------------------------------------------------|-----|------------------------------------------------------------------------------------------------|
| Communication entre 2 logiciels                 | 6   | Front statique ↔ API Flask (REST JSON), + Flask ↔ API Spotify (OAuth + REST).                  |
| BDD ≥ 3 tables                                  | 3   | 5 tables relationnelles avec FK, index, contraintes UNIQUE.                                    |
| Algorithme avancé                               | 3   | Content-based filtering + cosine similarity + injection exotique paramétrable.                 |
| Interaction utilisateur                         | 2   | Boutons play/like/dislike/add, slider curiosité, modales, animations swipe.                    |
| CRUD complet                                    | 2   | Playlists : C/R/U/D + ajout/retrait de morceaux.                                               |
| Cahier des charges                              | 4   | Ce document.                                                                                   |
| **Total fonctionnalités obligatoires**          | 20  |                                                                                                |
| **Fonctionnalités projet 4**                    |     |                                                                                                |
| Client de navigation                            | 3   | Pages `index`, `main`, `profil` + header dynamique selon authentification.                     |
| Algo de recommandation (filtrage)               | 5   | Cf. ci-dessus + slider de paramétrage par utilisateur.                                         |
| Serveur d'analyse / sync profils                | 4   | API Flask centralisée + OAuth Spotify avec refresh automatique.                                |
| Import CSV catalogue                            | 2   | Endpoint `/api/catalog/import` + script `seed.py`.                                             |
| CRUD playlists                                  | 4   | Cf. ci-dessus.                                                                                 |
| **Total**                                       | 38  | **(28 pts visés au minimum)**                                                                  |

---

## 7. Planning & livraison

| Date           | Étape                                                 |
|----------------|-------------------------------------------------------|
| 06 mars 2026   | Dépôt du cahier des charges sur Moodle.               |
| Mars - avril   | Conception (UML, schéma BDD), développement front + back, intégration Spotify. |
| 28 avril 2026  | Soutenance orale (15 min + 5 min Q&R), démo live, dépôt Git final. |

---

## 8. Risques & limites identifiés

* **Comptes Spotify gratuits** : ne peuvent pas utiliser le Web Playback SDK
  pour la lecture intégrale. **Mitigation** : on utilise les preview 30 s qui
  marchent pour tous les comptes.
* **Preview URLs absentes** : Spotify ne fournit plus systématiquement de
  preview pour tous les morceaux. **Mitigation** : le front affiche un toast
  d'erreur et le morceau reste likable / ajoutable malgré tout.
* **Démarrage à froid** : un nouvel utilisateur n'a aucune donnée pour
  alimenter l'algo. **Mitigation** : fallback sur des morceaux populaires de
  genres distincts.
* **Volumétrie** : l'algo charge tout le catalogue en mémoire à chaque appel.
  Acceptable pour un catalogue de quelques milliers de tracks ; au-delà il
  faudrait précalculer une matrice creuse en cache.
