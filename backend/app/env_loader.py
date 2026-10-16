"""
env_loader.py
=============
Lightweight, zero-dependency .env loader for Debug Dojo backend.
Reads KEY=VALUE pairs into os.environ without requiring external packages.
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


def load_env(env_path: str | None = None) -> bool:
    """
    Search for and load .env into os.environ.
    Tries specified path, then backend/.env, then project root .env.
    Does NOT overwrite existing environment variables.
    """
    candidates = []
    if env_path:
        candidates.append(env_path)
    else:
        # 1. backend/.env
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(here, ".env"))
        # 2. repo root .env
        repo_root = os.path.dirname(here)
        candidates.append(os.path.join(repo_root, ".env"))

    loaded = False
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
                logger.info("Loaded environment variables from %s", path)
                loaded = True
                break
            except Exception as exc:
                logger.warning("Could not read %s: %s", path, exc)

    return loaded
