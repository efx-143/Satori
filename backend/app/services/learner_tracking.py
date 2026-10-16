"""
learner_tracking.py
====================
Debug Dojo – Recurring Mistakes Engine & Mastery Scoring
----------------------------------------------------------
Provides two public functions:

    check_recurring_mistake(learner_id, current_mistake_tags, current_challenge_id)
        → RecurringMistakeResult

    update_mastery_score(learner_id, concept_tags, is_passed, hints_used_count)
        → list[MasteryUpdateResult]

All DB writes are committed inside the functions; callers do not need to
manage transactions.

Mastery Scoring Model
---------------------
Score range: 0.0 – 100.0 (floats, stored in ConceptMastery.mastery_score)

On a PASS:
  base_gain = 15.0 points
  hint_weight = hint_decay_factor(hints_used_count)   # see table below
  diminishing_return = 1.0 - (current_score / 100.0)  # slows near 100
  delta = base_gain × hint_weight × diminishing_return

  hint_decay_factor:
    0 hints → 1.00  (full reward — solved independently)
    1 hint  → 0.70  (good but needed a nudge)
    2 hints → 0.45  (moderate dependence)
    3 hints → 0.25  (significant scaffolding)
    4+hints → 0.10  (heavy scaffolding)

On a FAIL:
  delta = -2.0 × (current_score / 100.0 + 0.1)  # proportional decay
  (clamped: score never goes below 0.0)

Recurring Mistake Engine
------------------------
A mistake tag is "recurring" if it appears in submissions for at least
one OTHER challenge (different challenge_id) by the same learner.

The engine recommends the easiest published challenge that:
  1. Covers the recurring mistake's associated concept tags.
  2. Has NOT been passed by this learner yet.
  3. Preferring lower difficulty (Easy > Medium > Hard).
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any

from app import db
from app.models.submission import Submission
from app.models.concept_mastery import ConceptMastery
from app.models.challenge import Challenge

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Minimum number of distinct challenges on which a tag must appear
# before it is labelled "recurring".
_RECURRENCE_THRESHOLD: int = 1   # appears on ≥ 2 different challenges

# Dynamic score weights indexed by hints_used_count (capped at index 4)
_HINT_DECAY: list[float] = [1.00, 0.70, 0.45, 0.25, 0.10]

# Base score gain per concept on a clean pass
_BASE_GAIN: float = 15.0

# Proportional decay on a fail (multiplied by score-relative factor)
_BASE_DECAY: float = 2.0

# Minimum score after decay (never below this)
_SCORE_FLOOR: float = 0.0

# Maximum score
_SCORE_CEILING: float = 100.0

# Concept tags that each AST mistake tag maps to
# (used to find remedial challenges)
_MISTAKE_TO_CONCEPTS: dict[str, list[str]] = {
    "off_by_one":            ["loops", "slicing", "indexing"],
    "unhandled_short_input": ["lists", "conditionals"],
    "print_not_return":      ["functions"],
    "boundary_comparison":   ["conditionals", "arithmetic"],
    "mutates_input":         ["lists"],
}

_DIFFICULTY_ORDER: dict[str, int] = {"Easy": 0, "Medium": 1, "Hard": 2}


# ─────────────────────────────────────────────────────────────────────────────
# Data-classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecurringTag:
    """Details about one recurring mistake tag."""

    tag: str
    """The mistake slug, e.g. 'off_by_one'."""

    occurrences: int
    """Number of distinct challenges on which this tag previously appeared."""

    previous_challenge_ids: list[str]
    """The other challenge IDs where this tag was seen."""

    suggested_challenge_id: str | None = None
    """Slug of the recommended next challenge to fix this weakness, or None."""

    suggested_challenge_title: str | None = None
    """Human-readable title of the suggested challenge."""

    suggested_challenge_difficulty: str | None = None

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "occurrences": self.occurrences,
            "previous_challenge_ids": self.previous_challenge_ids,
            "suggested_challenge_id": self.suggested_challenge_id,
            "suggested_challenge_title": self.suggested_challenge_title,
            "suggested_challenge_difficulty": self.suggested_challenge_difficulty,
        }


@dataclass
class RecurringMistakeResult:
    """Returned by check_recurring_mistake()."""

    has_recurring: bool
    """True if at least one tag is recurring."""

    recurring_tags: list[RecurringTag] = field(default_factory=list)
    """Details for every recurring tag found."""

    non_recurring_tags: list[str] = field(default_factory=list)
    """Tags present in current submission that are NOT yet recurring."""

    def to_dict(self) -> dict:
        return {
            "has_recurring": self.has_recurring,
            "recurring_tags": [rt.to_dict() for rt in self.recurring_tags],
            "non_recurring_tags": self.non_recurring_tags,
        }


@dataclass
class MasteryUpdateResult:
    """Result for a single concept tag after update_mastery_score()."""

    concept_tag: str
    previous_score: float
    new_score: float
    delta: float
    action: str     # "increased" | "decreased" | "unchanged"
    hints_weight_applied: float | None = None   # None on fail

    def to_dict(self) -> dict:
        return {
            "concept_tag": self.concept_tag,
            "previous_score": round(self.previous_score, 2),
            "new_score": round(self.new_score, 2),
            "delta": round(self.delta, 2),
            "action": self.action,
            "hints_weight_applied": self.hints_weight_applied,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hint_decay_factor(hints_used: int) -> float:
    """
    Return the score multiplier based on how many hints the learner used.

    hints_used → weight
    0          → 1.00  (solved without any hints — maximum reward)
    1          → 0.70
    2          → 0.45
    3          → 0.25
    4+         → 0.10  (heavy scaffolding — minimum reward for passing)
    """
    idx = min(hints_used, len(_HINT_DECAY) - 1)
    return _HINT_DECAY[idx]


def _compute_pass_delta(current_score: float, hints_used: int) -> tuple[float, float]:
    """
    Compute score gain on a pass with diminishing returns.

    Returns (delta, weight_applied).
    """
    weight = _hint_decay_factor(hints_used)
    diminishing = 1.0 - (current_score / _SCORE_CEILING)
    # Ensure at least a tiny gain (0.5 pt) even at high mastery
    diminishing = max(diminishing, 0.03)
    delta = _BASE_GAIN * weight * diminishing
    return round(delta, 4), weight


def _compute_fail_delta(current_score: float) -> float:
    """
    Compute score loss on a fail — proportional to current score so that
    beginners lose less than advanced learners from a single failure.
    """
    proportional = current_score / _SCORE_CEILING + 0.1
    delta = -(_BASE_DECAY * proportional)
    return round(delta, 4)


def _get_or_create_mastery(learner_id: str, concept_tag: str) -> ConceptMastery:
    """
    Fetch the ConceptMastery row for (learner_id, concept_tag),
    creating it if it does not yet exist.
    Does NOT commit.
    """
    record = ConceptMastery.query.filter_by(
        learner_id=learner_id,
        concept_tag=concept_tag,
    ).first()

    if record is None:
        record = ConceptMastery(
            learner_id=learner_id,
            concept_tag=concept_tag,
            mastery_score=0.0,
            attempts=0,
            correct_attempts=0,
        )
        db.session.add(record)
        db.session.flush()   # assign id without committing

    return record


def _find_remedial_challenge(
    learner_id: str,
    concept_targets: list[str],
    exclude_challenge_id: str,
) -> Challenge | None:
    """
    Find the best remedial challenge for the given concept targets.

    Selection criteria (in priority order):
      1. Challenge is published.
      2. Challenge concept_tags overlaps with concept_targets.
      3. The learner has NOT yet submitted a passing solution.
      4. Sorted by difficulty (Easy first).
      5. Excludes the current challenge.
    """
    # IDs of challenges this learner has already passed
    passed_ids: set[str] = set(
        row.challenge_id
        for row in Submission.query.filter_by(
            learner_id=learner_id,
            outcome="passed",
        ).with_entities(Submission.challenge_id).all()
    )
    passed_ids.add(exclude_challenge_id)

    candidates = Challenge.query.filter_by(is_published=True).all()
    scored: list[tuple[int, Challenge]] = []

    for ch in candidates:
        if ch.id in passed_ids:
            continue
        tags = set(ch.concept_tags or [])
        overlap = tags.intersection(concept_targets)
        if not overlap:
            continue
        diff_score = _DIFFICULTY_ORDER.get(ch.difficulty, 99)
        # More overlap = lower (better) score; tiebreak on difficulty
        scored.append((-len(overlap), diff_score, ch))

    if not scored:
        return None

    scored.sort(key=lambda t: (t[0], t[1]))
    return scored[0][2]


# ─────────────────────────────────────────────────────────────────────────────
# Public API – Task 3: check_recurring_mistake
# ─────────────────────────────────────────────────────────────────────────────

def check_recurring_mistake(
    learner_id: str,
    current_mistake_tags: list[str],
    current_challenge_id: str,
) -> RecurringMistakeResult:
    """
    Detect recurring mistake patterns for a learner.

    A tag is "recurring" if it has appeared in previous submissions on at
    least one DIFFERENT challenge (i.e., it's not just a one-off mistake on
    this particular problem).

    For every recurring tag found, a remedial challenge is suggested.

    Parameters
    ----------
    learner_id : str
        UUID of the learner.
    current_mistake_tags : list[str]
        AST mistake tags from the current submission (e.g. ["off_by_one"]).
    current_challenge_id : str
        Slug of the current challenge (excluded from history search).

    Returns
    -------
    RecurringMistakeResult
        Contains recurring tags with suggested remedial challenges and
        non-recurring tags.
    """
    if not current_mistake_tags:
        return RecurringMistakeResult(has_recurring=False)

    # ── Fetch all past submissions for this learner on OTHER challenges ───────
    past_submissions = (
        Submission.query
        .filter(
            Submission.learner_id == learner_id,
            Submission.challenge_id != current_challenge_id,
        )
        .with_entities(Submission.challenge_id, Submission.mistake_tags)
        .all()
    )

    # Build: tag → set of challenge_ids where it appeared
    tag_to_challenges: dict[str, set[str]] = {}
    for cid, tags in past_submissions:
        if not tags:
            continue
        for tag in tags:
            tag_to_challenges.setdefault(tag, set()).add(cid)

    recurring_tags: list[RecurringTag] = []
    non_recurring:  list[str] = []

    for tag in current_mistake_tags:
        prev_challenges = tag_to_challenges.get(tag, set())
        occurrence_count = len(prev_challenges)

        if occurrence_count >= _RECURRENCE_THRESHOLD:
            # ── Recurring: find a remedial challenge ──────────────────────────
            concept_targets = _MISTAKE_TO_CONCEPTS.get(tag, ["lists"])
            suggestion = _find_remedial_challenge(
                learner_id, concept_targets, current_challenge_id
            )

            recurring_tags.append(RecurringTag(
                tag=tag,
                occurrences=occurrence_count,
                previous_challenge_ids=sorted(prev_challenges),
                suggested_challenge_id=(suggestion.id if suggestion else None),
                suggested_challenge_title=(suggestion.title if suggestion else None),
                suggested_challenge_difficulty=(
                    suggestion.difficulty if suggestion else None
                ),
            ))
            logger.info(
                "Recurring mistake '%s' for learner %s: seen on %d other challenge(s). "
                "Suggested: %s",
                tag, learner_id, occurrence_count,
                suggestion.id if suggestion else "none",
            )
        else:
            non_recurring.append(tag)

    return RecurringMistakeResult(
        has_recurring=bool(recurring_tags),
        recurring_tags=recurring_tags,
        non_recurring_tags=non_recurring,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API – Task 4: update_mastery_score
# ─────────────────────────────────────────────────────────────────────────────

def update_mastery_score(
    learner_id: str,
    concept_tags: list[str],
    is_passed: bool,
    hints_used_count: int,
) -> list[MasteryUpdateResult]:
    """
    Update the ConceptMastery score for every concept in concept_tags.

    Scoring rules
    -------------
    PASS:
        delta = BASE_GAIN × hint_weight × (1 − score/100)
        hint_weight = [1.0, 0.70, 0.45, 0.25, 0.10] for [0,1,2,3,4+] hints

        Example:
          score=20, hints=0 → delta = 15 × 1.00 × 0.80 = 12.0
          score=20, hints=2 → delta = 15 × 0.45 × 0.80 =  5.4
          score=80, hints=0 → delta = 15 × 1.00 × 0.20 =  3.0  (diminishing)

    FAIL:
        delta = −BASE_DECAY × (score/100 + 0.1)
        Clamped at SCORE_FLOOR (0.0).

    Parameters
    ----------
    learner_id : str
        UUID of the learner.
    concept_tags : list[str]
        Tags from the challenge (e.g. ["lists", "slicing", "arithmetic"]).
    is_passed : bool
        Whether the submission passed all test cases.
    hints_used_count : int
        Number of hints the learner requested before submitting.

    Returns
    -------
    list[MasteryUpdateResult]
        One result per concept tag with before/after scores and delta.
    """
    results: list[MasteryUpdateResult] = []
    now = datetime.datetime.utcnow()

    for tag in concept_tags:
        record = _get_or_create_mastery(learner_id, tag)
        prev_score = record.mastery_score

        if is_passed:
            delta, weight = _compute_pass_delta(prev_score, hints_used_count)
            new_score = min(_SCORE_CEILING, prev_score + delta)
            record.correct_attempts += 1
            action = "increased"
        else:
            delta = _compute_fail_delta(prev_score)
            new_score = max(_SCORE_FLOOR, prev_score + delta)
            weight = None
            action = "decreased" if new_score < prev_score else "unchanged"

        record.mastery_score    = round(new_score, 4)
        record.attempts         += 1
        record.last_attempted_at = now
        record.updated_at       = now

        results.append(MasteryUpdateResult(
            concept_tag=tag,
            previous_score=round(prev_score, 2),
            new_score=round(new_score, 2),
            delta=round(delta, 2),
            action=action,
            hints_weight_applied=weight,
        ))

        logger.debug(
            "Mastery update [%s] concept='%s': %.2f → %.2f (Δ%.2f, hints=%d)",
            learner_id, tag, prev_score, new_score, delta, hints_used_count,
        )

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Failed to commit mastery update for learner %s: %s", learner_id, exc)
        raise

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Utility: get a learner's full mastery profile
# ─────────────────────────────────────────────────────────────────────────────

def get_mastery_profile(learner_id: str) -> list[dict]:
    """
    Return all ConceptMastery records for a learner, sorted by score descending.

    Useful for the learner dashboard and for AI-tutor context.
    """
    records = (
        ConceptMastery.query
        .filter_by(learner_id=learner_id)
        .order_by(ConceptMastery.mastery_score.desc())
        .all()
    )
    return [r.to_dict() for r in records]


def get_weakest_concepts(learner_id: str, top_n: int = 3) -> list[str]:
    """
    Return the concept_tags with the lowest mastery scores.

    Used by the AI tutor to focus explanations on weak areas.
    """
    records = (
        ConceptMastery.query
        .filter_by(learner_id=learner_id)
        .order_by(ConceptMastery.mastery_score.asc())
        .limit(top_n)
        .all()
    )
    return [r.concept_tag for r in records]


def get_all_recurring_mistakes(learner_id: str) -> list[dict]:
    """
    Find all recurring mistake tags across all submissions for a learner.
    A tag is recurring if it has appeared in submissions for >= 2 distinct challenges.
    """
    past_submissions = (
        Submission.query
        .filter(Submission.learner_id == learner_id)
        .with_entities(Submission.challenge_id, Submission.mistake_tags)
        .all()
    )
    tag_to_challenges: dict[str, set[str]] = {}
    for cid, tags in past_submissions:
        if not tags:
            continue
        for tag in tags:
            tag_to_challenges.setdefault(tag, set()).add(cid)

    recurring_list: list[dict] = []
    for tag, cids in tag_to_challenges.items():
        if len(cids) >= 2:
            concept_targets = _MISTAKE_TO_CONCEPTS.get(tag, ["lists"])
            suggestion = _find_remedial_challenge(learner_id, concept_targets, "")
            recurring_list.append({
                "tag": tag,
                "occurrences": len(cids),
                "previous_challenge_ids": sorted(cids),
                "suggested_challenge_id": suggestion.id if suggestion else None,
                "suggested_challenge_title": suggestion.title if suggestion else None,
                "suggested_challenge_difficulty": suggestion.difficulty if suggestion else None,
            })
    return recurring_list
