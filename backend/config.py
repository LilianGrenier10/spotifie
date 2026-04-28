"""
Configuration centrale de l'application.
Charge les variables d'environnement depuis .env et les expose
en attributs typés.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charge .env si présent
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Configuration globale - lecture seule."""

    # Spotify OAuth
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI: str = os.getenv(
        "SPOTIFY_REDIRECT_URI",
        # ATTENTION : Spotify refuse "localhost" depuis 2024.
        # Il faut OBLIGATOIREMENT 127.0.0.1.
        "http://127.0.0.1:5000/api/auth/spotify/callback",
    )
    SPOTIFY_SCOPE: str = (
        "user-read-email user-read-private "
        "playlist-modify-public playlist-modify-private "
        "user-library-read user-top-read"
    )

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXP_HOURS: int = 24 * 7  # 7 jours

    # Flask
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "1") == "1"

    # Chemins
    BASE_DIR: Path = BASE_DIR
    DB_PATH: Path = Path(
        os.getenv("SPOTIFIE_DB_PATH", str(BASE_DIR / "data" / "spotifie.db"))
    )
    CATALOG_CSV: Path = BASE_DIR / "data" / "catalog.csv"
    STATIC_DIR: Path = BASE_DIR.parent / "static"
    JS_DIR: Path = BASE_DIR.parent / "JS"
    IMG_DIR: Path = BASE_DIR.parent / "img"

    @classmethod
    def spotify_configured(cls) -> bool:
        """True si les identifiants Spotify sont renseignés."""
        return bool(cls.SPOTIFY_CLIENT_ID and cls.SPOTIFY_CLIENT_SECRET)


config = Config()
