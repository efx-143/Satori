"""
ConceptMastery model – tracks per-learner mastery score for each concept.
"""
import datetime
import uuid

from app import db


class ConceptMastery(db.Model):
    __tablename__ = "concept_masteries"

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

    # ── Concept identification ────────────────────────────────────────────────
    concept_tag = db.Column(db.String(80), nullable=False, index=True)
    # e.g. "loops", "lists", "recursion", "strings", "dicts", "sorting"

    # ── Mastery metrics ───────────────────────────────────────────────────────
    mastery_score = db.Column(
        db.Float, nullable=False, default=0.0
    )
    # 0.0 – 100.0; updated after each submission judgment
    attempts = db.Column(db.Integer, nullable=False, default=0)
    correct_attempts = db.Column(db.Integer, nullable=False, default=0)
    last_attempted_at = db.Column(db.DateTime, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.datetime.utcnow
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    # ── Constraints ───────────────────────────────────────────────────────────
    __table_args__ = (
        db.UniqueConstraint("learner_id", "concept_tag", name="uq_learner_concept"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    learner = db.relationship("Learner", back_populates="concept_masteries")

    def __repr__(self) -> str:
        return (
            f"<ConceptMastery learner={self.learner_id!r} "
            f"concept={self.concept_tag!r} score={self.mastery_score:.1f}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "learner_id": self.learner_id,
            "concept_tag": self.concept_tag,
            "mastery_score": self.mastery_score,
            "attempts": self.attempts,
            "correct_attempts": self.correct_attempts,
            "last_attempted_at": (
                self.last_attempted_at.isoformat()
                if self.last_attempted_at
                else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
