"""
Point d'entrée Flask de SPOTIFIÉ.

Lance :
    python -m backend.app
ou :
    cd backend && python app.py
"""
import os
import sys
from pathlib import Path

# Permet `python backend/app.py` ET `python -m backend.app`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, send_from_directory, redirect
from flask_cors import CORS

from backend.config import config
from backend.database import init_db
from backend.routes.auth_routes import bp as auth_bp
from backend.routes.tracks_routes import bp as tracks_bp
from backend.routes.playlists_routes import bp as playlists_bp
from backend.routes.recommendations_routes import bp as reco_bp
from backend.routes.catalog_routes import bp as catalog_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(config.STATIC_DIR),
        static_url_path="",  # sert /index.html, /index.css, etc.
    )
    CORS(app, supports_credentials=True)

    # Initialise la BDD au démarrage
    init_db()

    # Blueprints API
    app.register_blueprint(auth_bp)
    app.register_blueprint(tracks_bp)
    app.register_blueprint(playlists_bp)
    app.register_blueprint(reco_bp)
    app.register_blueprint(catalog_bp)

    # ----- Routes statiques -----
    @app.get("/")
    def root():
        return redirect("/index.html")

    @app.get("/JS/<path:filename>")
    def serve_js(filename):
        return send_from_directory(config.JS_DIR, filename)

    @app.get("/img/<path:filename>")
    def serve_img(filename):
        return send_from_directory(config.IMG_DIR, filename)

    @app.get("/api/health")
    def health():
        return {"ok": True, "spotify": config.spotify_configured()}

    return app


app = create_app()


if __name__ == "__main__":
    print(f" * SPOTIFIÉ démarre sur http://127.0.0.1:{config.FLASK_PORT}")
    print(f" * BDD : {config.DB_PATH}")
    print(f" * Spotify configuré : {config.spotify_configured()}")
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
