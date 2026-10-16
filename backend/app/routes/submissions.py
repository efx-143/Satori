"""
routes/submissions.py
======================
POST /api/v1/submissions/              Submit code — THE JUDGING LOOP
GET  /api/v1/submissions/<id>          Fetch one submission result
GET  /api/v1/submissions/learner/<lid> Learner's submission history

The judging loop (POST /):
  1. Validate request body
  2. Load challenge + test cases from DB
  3. Run code in sandbox via TestRunner
  4. Detect structural mistakes via mistake_detector
  5. Generate AI explanation via ai_tutor
  6. Detect recurring mistakes & update mastery via learner_tracking
  7. Persist Submission row
  8. Update learner XP + streak
  9. Return unified response
"""
from __future__ import annotations

import datetime
import logging

from flask import Blueprint, jsonify, request, abort

from app import db
from app.models.challenge  import Challenge
from app.models.learner    import Learner
from app.models.submission import Submission
from app.models.test_case  import TestCase
from app.services.test_runner      import get_runner
from app.utils.mistake_detector    import detect_mistakes
from app.services.ai_tutor         import generate_explanation, ExplanationResult
from app.services.learner_tracking import (
    check_recurring_mistake,
    update_mastery_score,
)

logger = logging.getLogger(__name__)
bp = Blueprint("submissions", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _xp_for_submission(
    outcome: str,
    base_xp: int,
    hints_used: int,
    is_first_pass: bool,
) -> int:
    """
    Compute XP to award:
      - Pass with 0 hints:  full base_xp + first-pass bonus
      - Pass with 1 hint:   70 % of base
      - Pass with 2 hints:  45 %
      - Pass with 3+ hints: 25 %
      - Fail:               0
    """
    if outcome != "passed":
        return 0
    weights = [1.0, 0.70, 0.45, 0.25]
    w = weights[min(hints_used, len(weights) - 1)]
    xp = round(base_xp * w)
    if is_first_pass and hints_used == 0:
        xp += round(base_xp * 0.5)   # 50 % first-pass bonus
    return xp


def _build_test_case_payload(test_cases: list[TestCase]) -> list[dict]:
    """Convert ORM TestCase objects to the format expected by TestRunner."""
    return [
        {
            "test_id":         tc.id,
            "input_args":      tc.input_args,
            "expected_output": tc.expected_output,
            "is_hidden":       tc.is_hidden,
        }
        for tc in test_cases
    ]


def _build_challenge_details(ch: Challenge) -> dict:
    """
    Build the challenge_details dict consumed by ai_tutor.
    Includes semantic labels for test cases (but not their values).
    """
    tc_labels = {}
    for tc in ch.test_cases:
        tc_labels[tc.id] = {
            "label":     getattr(tc, "label", "") or "",
            "is_hidden": tc.is_hidden,
        }
    return {
        "id":                 ch.id,
        "title":              ch.title,
        "description":        ch.description,
        "function_signature": ch.function_signature,
        "concept_tags":       ch.concept_tags or [],
        "difficulty":         ch.difficulty,
        "test_case_labels":   tc_labels,
    }


def _is_first_pass(learner_id: str, challenge_id: str) -> bool:
    """True if the learner has never passed this challenge before."""
    return not Submission.query.filter_by(
        learner_id=learner_id,
        challenge_id=challenge_id,
        outcome="passed",
    ).first()


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/submissions/  — THE JUDGING LOOP
# ─────────────────────────────────────────────────────────────────────────────

@bp.post("/")
def submit_code():
    """
    Core judging endpoint.

    Request body (JSON):
    {
        "learner_id":    "<uuid>",
        "challenge_id":  "last-k-total",
        "code":          "def last_k_total(marks, k): ...",
        "hints_used":    0          // number of hints the learner requested
    }

    Response (JSON):
    {
        "submission_id":    "<uuid>",
        "outcome":          "passed" | "failed" | "error" | "timeout",
        "passed_tests":     7,
        "total_tests":      10,
        "test_results":     [...],     // visible: full detail; hidden: outcome only
        "explanation":      {...},     // AI-generated why-it-failed
        "hint_ladder":      null,      // null on pass; populated on fail
        "mistake_tags":     [...],
        "recurring":        {...},
        "mastery_updates":  [...],
        "xp_awarded":       25,
        "new_total_xp":     150,
        "execution_ms":     null | float
    }
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Request body must be JSON.")

    # ── 1. Validate input ─────────────────────────────────────────────────────
    learner_id   = body.get("learner_id",   "").strip()
    challenge_id = body.get("challenge_id", "").strip()
    code         = body.get("code",         "").strip()
    hints_used   = int(body.get("hints_used", 0))

    if not learner_id:
        abort(400, description="'learner_id' is required.")
    if not challenge_id:
        abort(400, description="'challenge_id' is required.")
    if not code:
        abort(400, description="'code' is required.")
    if hints_used < 0:
        abort(400, description="'hints_used' must be ≥ 0.")

    # ── 2. Load entities ──────────────────────────────────────────────────────
    learner = Learner.query.get(learner_id)
    if not learner:
        abort(404, description=f"Learner '{learner_id}' not found.")

    challenge = Challenge.query.filter_by(
        id=challenge_id, is_published=True
    ).first_or_404(description=f"Challenge '{challenge_id}' not found.")

    test_cases = challenge.test_cases
    if not test_cases:
        abort(500, description="Challenge has no test cases configured.")

    # ── 3. Run sandbox ────────────────────────────────────────────────────────
    fn_name     = _extract_fn_name(challenge.function_signature)
    tc_payload  = _build_test_case_payload(test_cases)

    try:
        run_result = get_runner().run(code=code, fn_name=fn_name, test_cases=tc_payload)
    except Exception as exc:
        logger.error("Sandbox error for challenge %s: %s", challenge_id, exc)
        abort(500, description=f"Code execution failed: {exc}")

    # Map RunResult outcome → Submission.outcome enum value
    outcome_map = {
        "passed":       "passed",
        "failed":       "failed",
        "error":        "error",
        "timeout":      "timeout",
    }
    raw_outcome = run_result.overall_outcome
    db_outcome  = outcome_map.get(raw_outcome, "error")

    # ── 4. Detect structural mistakes (AST) ───────────────────────────────────
    if db_outcome != "passed":
        mistake_result = detect_mistakes(code)
        mistake_tags   = mistake_result.tags
    else:
        mistake_tags   = []

    # ── 5. Build enriched test results for AI (labels attached) ──────────────
    label_map: dict[str, str] = {
        tc.id: (getattr(tc, "label", "") or "")
        for tc in test_cases
    }
    enriched_results: list[dict] = []
    for tcr in run_result.test_results:
        d = tcr.to_dict()
        d["label"] = label_map.get(tcr.test_id, "")
        enriched_results.append(d)

    # ── 6a. Generate AI explanation ───────────────────────────────────────────
    challenge_details = _build_challenge_details(challenge)
    explanation = generate_explanation(
        challenge_details=challenge_details,
        submission_code=code,
        test_results=enriched_results,
        mistake_tags=mistake_tags,
    )

    # ── 6b. Recurring mistakes + mastery scoring ──────────────────────────────
    recurring_result = check_recurring_mistake(
        learner_id=learner_id,
        current_mistake_tags=mistake_tags,
        current_challenge_id=challenge_id,
    )

    concept_tags = challenge.concept_tags or []
    mastery_updates = update_mastery_score(
        learner_id=learner_id,
        concept_tags=concept_tags,
        is_passed=(db_outcome == "passed"),
        hints_used_count=hints_used,
    )

    # ── 7. Persist Submission ─────────────────────────────────────────────────
    first_pass = _is_first_pass(learner_id, challenge_id)
    xp_awarded = _xp_for_submission(
        outcome=db_outcome,
        base_xp=challenge.xp_reward,
        hints_used=hints_used,
        is_first_pass=first_pass,
    )

    avg_elapsed = None
    elapsed_vals = [
        r.elapsed_ms for r in run_result.test_results
        if r.elapsed_ms is not None
    ]
    if elapsed_vals:
        avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 2)

    submission = Submission(
        learner_id=learner_id,
        challenge_id=challenge_id,
        code=code,
        outcome=db_outcome,
        passed_tests=run_result.passed_tests,
        total_tests=run_result.total_tests,
        execution_time_ms=avg_elapsed,
        explanation=f"{explanation.summary}\n\n{explanation.body}",
        mistake_tags=mistake_tags,
        xp_awarded=xp_awarded,
    )
    db.session.add(submission)

    # ── 8. Update learner XP + streak ─────────────────────────────────────────
    if xp_awarded > 0:
        learner.xp_points = (learner.xp_points or 0) + xp_awarded
        # Update streak: if last activity was yesterday, increment; else reset
        today = datetime.date.today()
        if learner.last_active_date:
            last = learner.last_active_date.date() if hasattr(learner.last_active_date, "date") else learner.last_active_date
        else:
            last = None
        if last is None or last < today:
            if last == today - datetime.timedelta(days=1):
                learner.streak_days = (learner.streak_days or 0) + 1
            elif last != today:
                learner.streak_days = 1
            learner.last_active_date = datetime.datetime.utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("DB commit failed: %s", exc)
        abort(500, description="Failed to save submission.")

    # ── 9. Build response ─────────────────────────────────────────────────────
    return jsonify({
        "submission_id":   submission.id,
        "outcome":         db_outcome,
        "passed_tests":    run_result.passed_tests,
        "total_tests":     run_result.total_tests,
        "test_results":    [r.to_dict() for r in run_result.test_results],
        "explanation":     explanation.to_dict(),
        "hint_ladder":     None,   # populated lazily via GET /hints/<sub_id>
        "mistake_tags":    mistake_tags,
        "recurring":       recurring_result.to_dict(),
        "mastery_updates": [m.to_dict() for m in mastery_updates],
        "xp_awarded":      xp_awarded,
        "new_total_xp":    learner.xp_points,
        "execution_ms":    avg_elapsed,
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/submissions/<id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.get("/<string:submission_id>")
def get_submission(submission_id: str):
    """Fetch a stored submission by ID."""
    sub = Submission.query.get_or_404(
        submission_id, description="Submission not found."
    )
    return jsonify(sub.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/submissions/learner/<learner_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.get("/learner/<string:learner_id>")
def learner_history(learner_id: str):
    """
    Paginated submission history for a learner.

    Query params:
        challenge_id   filter by challenge (optional)
        outcome        filter by outcome   (optional)
        page           default 1
        per_page       default 20, max 50
    """
    _ = Learner.query.get_or_404(learner_id, description="Learner not found.")

    challenge_id = request.args.get("challenge_id")
    outcome      = request.args.get("outcome")
    page         = max(1,  request.args.get("page",     1,  type=int))
    per_page     = min(50, request.args.get("per_page", 20, type=int))

    q = Submission.query.filter_by(learner_id=learner_id)
    if challenge_id:
        q = q.filter_by(challenge_id=challenge_id)
    if outcome:
        q = q.filter_by(outcome=outcome)

    q = q.order_by(Submission.submitted_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "submissions": [s.to_dict() for s in pagination.items],
        "total":       pagination.total,
        "page":        page,
        "per_page":    per_page,
        "pages":       pagination.pages,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _extract_fn_name(function_signature: str) -> str:
    """
    Extract the function name from a signature string.
    e.g. "def last_k_total(marks, k):" → "last_k_total"
    """
    try:
        # "def foo(...)" → "foo"
        return function_signature.split("def ")[1].split("(")[0].strip()
    except (IndexError, AttributeError):
        return function_signature.strip()
