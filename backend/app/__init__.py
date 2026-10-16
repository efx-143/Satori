"""
Debug Dojo – Flask application factory.
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_object="app.config.DevelopmentConfig"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    with app.app_context():
        from app.models import learner, concept_mastery, challenge, test_case, submission  # noqa: F401
        db.create_all()

    return app
