"""
routes/__init__.py
Registers all blueprint prefixes on the Flask app.
"""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.challenges import bp as challenges_bp
    from app.routes.submissions import bp as submissions_bp
    from app.routes.learners import bp as learners_bp
    from app.routes.hints import bp as hints_bp

    app.register_blueprint(challenges_bp,  url_prefix="/api/v1/challenges")
    app.register_blueprint(submissions_bp, url_prefix="/api/v1/submissions")
    app.register_blueprint(learners_bp,    url_prefix="/api/v1/learners")
    app.register_blueprint(hints_bp,       url_prefix="/api/v1/hints")
