"""
routes/hints.py
================
POST /api/v1/hints/<submission_id>   Generate hint ladder for a submission
GET  /api/v1/hints/<submission_id>   Retrieve previously generated hints

Hints are generated lazily (on first request) and cached in the
Submission.explanation JSON field to avoid repeated LLM calls.
"""
from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, request, abort

from app import db
from app.models.submission import Submission
from app.models.challenge  import Challenge
from app.services.ai_tutor import generate_hint_ladder, ExplanationResult, HintLadder

logger = logging.getLogger(__name__)
bp = Blueprint("hints", __name__)

_HINT_CACHE_KEY = "__hint_ladder__"


def _load_cached_hints(submission: Submission) -> HintLadder | None:
    """
    Return previously generated HintLadder if cached inside the submission,
    otherwise None.  Hints are stored as a JSON block appended to the
    explanation field using a sentinel key.
    """
    if not submission.explanation:
        return None
    try:
        # Hints stored as JSON trailer after a sentinel line
        marker = f"\n\n{_HINT_CACHE_KEY}:"
        if marker in submission.explanation:
            json_str = submission.explanation.split(marker, 1)[1]
            d = json.loads(json_str)
            return HintLadder(
                hint_1=d["hint_1"],
                hint_2=d["hint_2"],
                hint_3=d["hint_3"],
                llm_used=d.get("llm_used", False),
            )
    except Exception:
        pass
    return None


def _cache_hints(submission: Submission, ladder: HintLadder) -> None:
    """Persist the hint ladder in the Submission.explanation field."""
    marker = f"\n\n{_HINT_CACHE_KEY}:"
    base = (submission.explanation or "").split(marker)[0]  # strip old hints
    submission.explanation = base + marker + json.dumps(ladder.to_dict())
    db.session.commit()


@bp.post("/<string:submission_id>")
def generate_hints(submission_id: str):
    """
    Generate (or re-fetch) the 3-hint ladder for a failed submission.

    Request body (JSON) — optional:
    {
        "force_regenerate": false   // set true to bypass cache
    }

    Response:
    {
        "submission_id": "...",
        "hint_1": "...",
        "hint_2": "...",
        "hint_3": "...",
        "cached": false,
        "llm_used": true
    }
    """
    body            = request.get_json(silent=True) or {}
    force_regen     = bool(body.get("force_regenerate", False))

    submission = Submission.query.get_or_404(
        submission_id, description="Submission not found."
    )

    # Only generate hints for failed submissions
    if submission.outcome == "passed":
        return jsonify({
            "submission_id": submission_id,
            "message": "Hints are not available for passing submissions.",
            "hint_1": None, "hint_2": None, "hint_3": None,
        }), 200

    # ── Check cache ───────────────────────────────────────────────────────────
    if not force_regen:
        cached = _load_cached_hints(submission)
        if cached:
            return jsonify({
                "submission_id": submission_id,
                **cached.to_dict(),
                "cached": True,
            })

    # ── Load challenge details ────────────────────────────────────────────────
    challenge = Challenge.query.get(submission.challenge_id)
    if not challenge:
        abort(404, description="Associated challenge not found.")

    challenge_details = {
        "id":                 challenge.id,
        "title":              challenge.title,
        "description":        challenge.description,
        "function_signature": challenge.function_signature,
        "concept_tags":       challenge.concept_tags or [],
        "difficulty":         challenge.difficulty,
    }

    # Reconstruct explanation text (without cached hints trailer)
    marker = f"\n\n{_HINT_CACHE_KEY}:"
    explanation_text = (submission.explanation or "").split(marker)[0]

    # ── Generate hints ────────────────────────────────────────────────────────
    ladder = generate_hint_ladder(
        challenge_details=challenge_details,
        submission_code=submission.code,
        explanation=explanation_text,
        mistake_tags=submission.mistake_tags or [],
    )

    # ── Cache and return ──────────────────────────────────────────────────────
    try:
        _cache_hints(submission, ladder)
    except Exception as exc:
        logger.warning("Could not cache hints for submission %s: %s", submission_id, exc)

    return jsonify({
        "submission_id": submission_id,
        **ladder.to_dict(),
        "cached": False,
    }), 201


@bp.get("/<string:submission_id>")
def get_hints(submission_id: str):
    """Return cached hints for a submission without regenerating."""
    submission = Submission.query.get_or_404(
        submission_id, description="Submission not found."
    )

    cached = _load_cached_hints(submission)
    if cached:
        return jsonify({
            "submission_id": submission_id,
            **cached.to_dict(),
            "cached": True,
        })

    return jsonify({
        "submission_id": submission_id,
        "message": "No hints generated yet. POST to this endpoint to generate.",
        "hint_1": None, "hint_2": None, "hint_3": None,
    }), 200
