"""
config.py — CryptoRisk shared configuration

Loads local secrets from `.env` (never committed) using plain Python —
no python-dotenv, since that library isn't on the project's allowed-libraries
list. Exposes simple module-level constants that db/, backend/, and frontend/
all import from.

Per FILE_STRUCTURE.md: no fixed owner. Whoever sets up the repo first writes
this file; everyone else just imports from it. If you need a new setting,
add it here and give the group a heads-up (config.py is a shared/conflict-
prone file).
"""

import os


def _load_env(filepath=".env"):
    """
    Minimal .env parser: reads KEY=VALUE lines into a dict.
    Skips blank lines, comments (#), and malformed lines with no '='.
    """
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


_env = _load_env()

# --- MySQL connection settings (used by db/connection.py -> get_connection()) ---
DB_HOST = _env.get("DB_HOST", "localhost")
DB_USER = _env.get("DB_USER", "root")
DB_PASSWORD = _env.get("DB_PASSWORD", '"pass"gv')
DB_NAME = _env.get("DB_NAME", "cryptorisk")

# --- CoinGecko API settings (used by backend/price_engine.py) ---
API_BASE_URL = _env.get("API_BASE_URL", "https://api.coingecko.com/api/v3")
API_KEY = _env.get("API_KEY", "")
