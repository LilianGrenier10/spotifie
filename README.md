# SPOTIFIÉ

> Projet Fil Rouge B2 Ynov Lille — Système de Recommandation Musicale (Projet 4)

Une application web qui apprend tes goûts musicaux et te propose **3
recommandations personnalisées** à chaque visite : 2 dans ta veine, 1
**découverte exotique** pour élargir ton univers. Connexion Spotify, lecture
30 s, création / export de playlists.

![stack](https://img.shields.io/badge/python-3.10+-blue) ![stack](https://img.shields.io/badge/flask-3-black) ![stack](https://img.shields.io/badge/scikit--learn-1.4-orange) ![stack](https://img.shields.io/badge/sqlite-3-lightgrey)

---

## ⚡️ Démarrage rapide

```bash
# 1. Cloner et installer les dépendances Python
cd backend
pip install -r requirements.txt

# 2. Configurer Spotify (optionnel mais recommandé pour la démo)
cp .env.example .env
# édite .env et renseigne SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET
# (créés sur https://developer.spotify.com/dashboard)
# Redirect URI à mettre dans l'app Spotify :
#   http://127.0.0.1:5000/api/auth/spotify/callback

# 3. Charger le catalogue de morceaux
python -m backend.seed
# (optionnel) Enrichir avec les vraies preview_url + audio features Spotify
python -m backend.enrich_with_spotify

# 4. Lancer l'application
python -m backend.app
```

Puis ouvre <http://127.0.0.1:5000> dans ton navigateur.

---

## 📁 Architecture

```
.
├── backend/                  # Serveur Flask + algo de reco
│   ├── app.py                # Point d'entrée
│   ├── config.py             # Lecture .env
│   ├── database.py           # SQLite + schéma
│   ├── auth.py               # bcrypt + JWT
│   ├── spotify_client.py     # Wrapper Spotipy
│   ├── recommender.py        # Algo content-based + exotique
│   ├── seed.py               # Charge data/catalog.csv en BDD
│   ├── enrich_with_spotify.py# Récupère vraies previews depuis Spotify
│   ├── data/
│   │   ├── catalog.csv       # 100 morceaux avec audio features
│   │   └── spotifie.db       # BDD SQLite (créée au démarrage)
│   └── routes/
│       ├── auth_routes.py
│       ├── tracks_routes.py
│       ├── playlists_routes.py
│       ├── recommendations_routes.py
│       └── catalog_routes.py
├── static/                   # Front HTML/CSS
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── main.html             # Page Découverte (3 recos)
│   ├── profil.html           # Page Mes Playlists
│   ├── header.html           # Inclus dynamiquement
│   ├── index.css
│   ├── main.css
│   └── profil.css
├── JS/
│   ├── api.js                # Client API (window.API)
│   ├── header-loader.js      # Header + auth state
│   ├── discover.js           # Logique page Découverte
│   ├── profil.js             # Logique page Playlists
│   └── playlist-unfolder.js  # (legacy, conservé)
├── img/                      # Assets graphiques
└── docs/
    ├── cahier-des-charges.md # Spécification fonctionnelle + technique
    └── uml.md                # Diagrammes UML (cas d'usage, classes, MCD)
```

---

## 🎯 Fonctionnalités

### Pour l'utilisateur

* **Inscription / connexion** locale (email + mot de passe).
* **Page de découverte** : 3 morceaux à chaque visite, dont **1 découverte
  exotique** d'un genre jamais exploré.
* **Lecture des extraits 30 s** directement dans le navigateur (Spotify
  preview_url + balise `<audio>` HTML5).
* **Like / Dislike / Skip** : chaque interaction affine le profil de goût.
* **Slider « Curiosité »** : règle la part de recommandations exotiques (0 % →
  100 %).
* **Création de playlists** + ajout/retrait de morceaux.
* **Connexion Spotify (OAuth)** + **export d'une playlist** vers le compte
  Spotify de l'utilisateur en un clic.

### Côté technique

* **5 tables relationnelles** (users, tracks, playlists, playlist_tracks,
  user_interactions) avec foreign keys et index.
* **CRUD complet** sur les playlists (Créer / Lire / MAJ / Supprimer).
* **Algorithme de recommandation** :
  * filtrage par contenu sur 8 audio features Spotify ;
  * vecteur de goût construit comme moyenne des likes − barycentre des
    dislikes ;
  * cosine similarity (scikit-learn) ;
  * injection d'une découverte exotique (genre non exploré) paramétrable ;
  * cold start : 3 morceaux populaires de genres distincts.
* **Auth** bcrypt + JWT en cookie HttpOnly.
* **OAuth Spotify** Authorization Code Flow + refresh token automatique.
* **Import CSV** : endpoint `/api/catalog/import` ou script `seed.py`.

---

## 🔑 Configuration Spotify

1. Va sur <https://developer.spotify.com/dashboard> et crée une application.
2. Dans les paramètres de l'app, ajoute la *Redirect URI* :
   ```
   http://127.0.0.1:5000/api/auth/spotify/callback
   ```
3. Copie le **Client ID** et le **Client Secret** dans `backend/.env` :
   ```
   SPOTIFY_CLIENT_ID=xxx
   SPOTIFY_CLIENT_SECRET=xxx
   ```
4. Lance `python -m backend.enrich_with_spotify` pour récupérer les vraies
   `preview_url` et audio features depuis Spotify.

L'application **fonctionne sans Spotify configuré** — tu peux faire la démo en
local avec le catalogue CSV (100 morceaux). Dans ce cas, l'export et la
connexion Spotify seront désactivés.

---

## 🧪 Tester rapidement

```bash
# Tests bout-en-bout via le test client de Flask
python -c "
from backend.app import app
c = app.test_client()
c.post('/api/auth/register', json={'email':'a@b.c','password':'azerty1'})
print(c.get('/api/recommendations').get_json())
"
```

Voir aussi `docs/cahier-des-charges.md` pour la spécification fonctionnelle et
`docs/uml.md` pour les diagrammes.

---

## 🧠 Équipe

* **Lilian Grenier** — backend Flask, algo de recommandation, intégration Spotify, documentation
* **Rodrigo Luyckx** — backend Flask, endpoints REST, intégration Spotify (avec Lilian)
* **Ruben Duriez** — base de données : modélisation relationnelle, schéma des 5 tables, requêtes SQL
* **Lucas Gosselin** — front-end : maquettes HTML/CSS, design system, composants visuels

Promotion INFO B2 — Ynov Lille — 2026.
