"""
Submission model – tracks every code submission by a learner.
"""
import datetime
import uuid

from sqlalchemy.dialects.sqlite import JSON

from app import db


class Submission(db.Model):
    __tablename__ = "submissions"

    # ── Primary key ──────────────────────────────────────────────────────────
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # ── Foreign keys ─────────────────────────────────────────────────────────
    learner_id = db.Column(
        db.String(36),
        db.ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_id = db.Column(
        db.String(80),
        db.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Submitted code ────────────────────────────────────────────────────────
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False, default="python")

    # ── Judgment outcome ──────────────────────────────────────────────────────
    outcome = db.Column(
        db.Enum(
            "passed",
            "failed",
            "error",
            "timeout",
            "pending",
            name="outcome_enum",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    passed_tests = db.Column(db.Integer, nullable=False, default=0)
    total_tests = db.Column(db.Integer, nullable=False, default=0)
    execution_time_ms = db.Column(db.Float, nullable=True)

    # ── AI / rule-based feedback ──────────────────────────────────────────────
    explanation = db.Column(db.Text, nullable=True)
    # Plain-English explanation of what went wrong or right.

    # ── Mistake taxonomy ─────────────────────────────────────────────────────
    # JSON array of detected mistake category strings, e.g.:
    # ["off_by_one", "print_not_return"]
    mistake_tags = db.Column(JSON, nullable=False, default=list)

    # ── XP awarded ───────────────────────────────────────────────────────────
    xp_awarded = db.Column(db.Integer, nullable=False, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    submitted_at = db.Column(
        db.DateTime, nullable=False, default=datetime.datetime.utcnow, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    learner = db.relationship("Learner", back_populates="submissions")
    challenge = db.relationship("Challenge", back_populates="submissions")

    def __repr__(self) -> str:
        return (
            f"<Submission learner={self.learner_id!r} "
            f"challenge={self.challenge_id!r} outcome={self.outcome!r}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "challenge_id": self.challenge_id,
            "code": self.code,
            "language": self.language,
            "outcome": self.outcome,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "execution_time_ms": self.execution_time_ms,
            "explanation": self.explanation,
            "mistake_tags": self.mistake_tags,
            "xp_awarded": self.xp_awarded,
            "submitted_at": self.submitted_at.isoformat(),
        }
