#!/usr/bin/env bash
# Script de lancement rapide pour la démo SPOTIFIÉ.
# Détecte automatiquement python3 / pip3 (macOS) ou python / pip (Linux/Windows).
set -e

cd "$(dirname "$0")"

# --- Détection des binaires Python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "❌ Aucun interpréteur Python trouvé."
    exit 1
fi

if command -v pip3 >/dev/null 2>&1; then
    PIP=pip3
elif command -v pip >/dev/null 2>&1; then
    PIP=pip
else
    PIP="$PYTHON -m pip"
fi

echo "==> Python : $($PYTHON --version)"

# --- Installation des dépendances ---
echo ""
echo "==> Installation des dépendances Python…"
$PIP install -q -r backend/requirements.txt || $PIP install --user -q -r backend/requirements.txt

# --- Configuration .env ---
if [ ! -f backend/.env ]; then
    echo ""
    echo "==> Création de backend/.env (copie depuis .env.example)…"
    cp backend/.env.example backend/.env
    echo "    ⚠️  Pour Spotify : remplis SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET"
fi

# --- Initialisation BDD + import du seed CSV (toujours, prouve l'import CSV) ---
echo ""
echo "==> Initialisation de la BDD + import du catalogue CSV (100 morceaux de référence)…"
$PYTHON -m backend.seed

# --- Construction du gros catalogue depuis iTunes (1ère exécution seulement) ---
if [ "${SKIP_BUILD:-0}" != "1" ] && [ ! -f backend/data/.catalog_built ]; then
    echo ""
    echo "==> Construction du gros catalogue depuis iTunes (~1000 morceaux, ~1 min)…"
    echo "    (skip avec SKIP_BUILD=1 ./run.sh ou en relançant — flag-file dans backend/data/)"
    $PYTHON -m backend.build_catalog && touch backend/data/.catalog_built

    # On enrichit aussi les morceaux du seed CSV (les 100 originaux n'ont pas de preview)
    echo ""
    echo "==> Enrichissement des morceaux du CSV (preview + pochettes manquantes)…"
    $PYTHON -m backend.enrich_with_itunes || true
fi

# --- Lancement du serveur ---
echo ""
echo "==> Lancement du serveur sur http://127.0.0.1:5000"
echo ""
$PYTHON -m backend.app
