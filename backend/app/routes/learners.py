"""
routes/learners.py
==================
POST /api/v1/learners/                 Register a new learner
GET  /api/v1/learners/<id>             Learner profile + stats
GET  /api/v1/learners/<id>/mastery     Concept mastery breakdown
GET  /api/v1/learners/<id>/dashboard   Full dashboard: profile + mastery + recent
"""
from __future__ import annotations

import datetime
import uuid

from flask import Blueprint, jsonify, request, abort

from app import db
from app.models.learner         import Learner
from app.models.concept_mastery import ConceptMastery
from app.models.submission      import Submission
from app.services.learner_tracking import (
    get_mastery_profile,
    get_weakest_concepts,
    get_all_recurring_mistakes,
)

bp = Blueprint("learners", __name__)


@bp.post("/")
def register_learner():
    """
    Register a new learner.

    Request body:
    {
        "username": "alice",
        "email":    "alice@example.com",    // optional
        "display_name": "Alice"             // optional
    }
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Request body must be JSON.")

    username = body.get("username", "").strip()
    if not username:
        abort(400, description="'username' is required.")

    # Check uniqueness
    if Learner.query.filter_by(username=username).first():
        abort(409, description=f"Username '{username}' is already taken.")

    learner = Learner(
        id=str(uuid.uuid4()),
        username=username,
        email=body.get("email", "").strip() or None,
        display_name=body.get("display_name", "").strip() or username,
        xp_points=0,
        streak_days=0,
    )
    db.session.add(learner)
    db.session.commit()

    return jsonify(learner.to_dict()), 201


@bp.get("/<string:learner_id>")
def get_learner(learner_id: str):
    """Return learner profile and aggregate statistics."""
    learner = Learner.query.get_or_404(learner_id, description="Learner not found.")

    # Aggregate stats from submissions
    total_subs  = Submission.query.filter_by(learner_id=learner_id).count()
    passed_subs = Submission.query.filter_by(
        learner_id=learner_id, outcome="passed"
    ).count()

    data = learner.to_dict()
    data["stats"] = {
        "total_submissions":  total_subs,
        "passed_submissions": passed_subs,
        "pass_rate":          round(passed_subs / total_subs, 3) if total_subs else 0.0,
    }
    return jsonify(data)


@bp.get("/<string:learner_id>/mastery")
def get_mastery(learner_id: str):
    """Return full concept mastery breakdown, sorted by score descending."""
    _ = Learner.query.get_or_404(learner_id, description="Learner not found.")
    profile = get_mastery_profile(learner_id)
    weakest = get_weakest_concepts(learner_id, top_n=3)
    return jsonify({
        "learner_id":     learner_id,
        "mastery":        profile,
        "weakest_topics": weakest,
    })


@bp.get("/<string:learner_id>/dashboard")
def dashboard(learner_id: str):
    """
    Full dashboard payload combining:
      - learner profile + stats
      - mastery breakdown + weakest concepts
      - last 5 submissions (summaries)
      - current streak
    """
    learner = Learner.query.get_or_404(learner_id, description="Learner not found.")

    # Stats
    total_subs  = Submission.query.filter_by(learner_id=learner_id).count()
    passed_subs = Submission.query.filter_by(
        learner_id=learner_id, outcome="passed"
    ).count()

    # Recent submissions (last 5, slim view)
    recent = (
        Submission.query
        .filter_by(learner_id=learner_id)
        .order_by(Submission.submitted_at.desc())
        .limit(5)
        .all()
    )
    recent_slim = [
        {
            "id":           s.id,
            "challenge_id": s.challenge_id,
            "outcome":      s.outcome,
            "passed_tests": s.passed_tests,
            "total_tests":  s.total_tests,
            "xp_awarded":   s.xp_awarded,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for s in recent
    ]

    # Mastery
    mastery = get_mastery_profile(learner_id)
    weakest = get_weakest_concepts(learner_id, top_n=3)

    # Recurring mistakes across all submissions
    recurring_mistakes = get_all_recurring_mistakes(learner_id)

    return jsonify({
        "learner":        learner.to_dict(),
        "stats": {
            "total_submissions":  total_subs,
            "passed_submissions": passed_subs,
            "pass_rate":          round(passed_subs / total_subs, 3) if total_subs else 0.0,
            "streak_days":        learner.streak_days or 0,
            "xp_points":          learner.xp_points  or 0,
        },
        "mastery":        mastery,
        "weakest_topics": weakest,
        "recent_submissions": recent_slim,
        "recurring_mistakes": recurring_mistakes,
    })
