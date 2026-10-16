"""
run.py — Debug Dojo development server entry point.

Usage:
    python run.py
    # or with gunicorn:
    gunicorn "run:app" --bind 0.0.0.0:5000 --workers 2
"""
from app.env_loader import load_env

load_env()

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development").lower() == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
