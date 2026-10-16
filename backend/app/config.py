"""
Debug Dojo – configuration classes.
"""
import os


def _get_database_uri(default: str = "sqlite:///debug_dojo.db") -> str:
    uri = os.environ.get("DATABASE_URL", default)
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "hackathon-debug-dojo-secret-key-2026")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _get_database_uri("sqlite:///debug_dojo.db")


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _get_database_uri("sqlite:///debug_dojo.db")
