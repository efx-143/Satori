"""
run.py — Debug Dojo development server entry point.

Usage:
    python run.py
    # or with gunicorn:
    gunicorn "run:app" --bind 0.0.0.0:5000 --workers 2
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
