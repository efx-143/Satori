"""
Debug Dojo – Flask application factory.
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()
logger = logging.getLogger(__name__)


def create_app(config_object: str = "app.config.DevelopmentConfig") -> Flask:
    from app.env_loader import load_env
    load_env()

    app = Flask(__name__)
    app.config.from_object(config_object)
    app.url_map.strict_slashes = False   # stop 308 redirects on missing trailing slash

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])  # allow Next.js dev

    # ── Database tables ───────────────────────────────────────────────────────
    with app.app_context():
        from app.models import (  # noqa: F401
            learner, concept_mastery, challenge, test_case, submission,
        )
        db.create_all()

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.routes import register_blueprints
    register_blueprints(app)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "debug-dojo-api"})

    # ── JSON error handlers ───────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(exc):
        return jsonify({"error": "bad_request",
                        "message": str(exc.description)}), 400

    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"error": "not_found",
                        "message": str(exc.description)}), 404

    @app.errorhandler(409)
    def conflict(exc):
        return jsonify({"error": "conflict",
                        "message": str(exc.description)}), 409

    @app.errorhandler(500)
    def internal(exc):
        logger.exception("Unhandled 500: %s", exc)
        return jsonify({"error": "internal_server_error",
                        "message": str(exc.description)}), 500

    return app
