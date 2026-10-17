"""
WSGI entrypoint for production deployments (e.g., Gunicorn, Render).
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
