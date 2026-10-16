"""
routes/challenges.py
======================
GET  /api/v1/challenges/               List all published challenges
GET  /api/v1/challenges/<id>           Get one challenge (no hidden tests)
GET  /api/v1/challenges/<id>/starter   Return starter code only
"""
from flask import Blueprint, jsonify, request

from app.models.challenge import Challenge

bp = Blueprint("challenges", __name__)


@bp.get("/")
def list_challenges():
    """
    List all published challenges.

    Query params:
        difficulty  Easy | Medium | Hard  (optional filter)
        concept     e.g. "lists"          (optional filter, substring match)
        page        int, default 1
        per_page    int, default 20, max 100
    """
    difficulty = request.args.get("difficulty")
    concept    = request.args.get("concept")
    page       = max(1, request.args.get("page",     1,  type=int))
    per_page   = min(100, request.args.get("per_page", 20, type=int))

    q = Challenge.query.filter_by(is_published=True)

    if difficulty:
        q = q.filter_by(difficulty=difficulty)

    if concept:
        # JSON field search — works for SQLite JSON and Postgres JSONB
        q = q.filter(Challenge.concept_tags.contains(concept))

    q = q.order_by(Challenge.difficulty.asc(), Challenge.id.asc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "challenges": [c.to_dict() for c in pagination.items],
        "total":      pagination.total,
        "page":       page,
        "per_page":   per_page,
        "pages":      pagination.pages,
    })


@bp.get("/<string:challenge_id>")
def get_challenge(challenge_id: str):
    """Return one published challenge (visible test cases only)."""
    ch = Challenge.query.filter_by(id=challenge_id, is_published=True).first_or_404(
        description=f"Challenge '{challenge_id}' not found."
    )
    return jsonify(ch.to_dict(include_hidden_tests=False))


@bp.get("/<string:challenge_id>/starter")
def get_starter(challenge_id: str):
    """Return just the starter code for a challenge."""
    ch = Challenge.query.filter_by(id=challenge_id, is_published=True).first_or_404()
    return jsonify({
        "challenge_id":       ch.id,
        "function_signature": ch.function_signature,
        "starter_code":       ch.starter_code,
    })
