"""
TestCase model – individual test cases tied to a Challenge.
"""
import datetime
import uuid

from sqlalchemy.dialects.sqlite import JSON

from app import db


class TestCase(db.Model):
    __tablename__ = "test_cases"

    # ── Primary key ──────────────────────────────────────────────────────────
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # ── Foreign keys ─────────────────────────────────────────────────────────
    challenge_id = db.Column(
        db.String(80),
        db.ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Test data ─────────────────────────────────────────────────────────────
    # input_args stores a JSON-serialisable list of positional arguments
    # that will be unpacked when calling the target function:
    #   function(*test_case.input_args)
    input_args = db.Column(JSON, nullable=False)
    expected_output = db.Column(JSON, nullable=False)

    # ── Visibility ────────────────────────────────────────────────────────────
    is_hidden = db.Column(db.Boolean, nullable=False, default=False, index=True)
    # Hidden tests are never shown to learners before submission.

    # ── Optional label ────────────────────────────────────────────────────────
    label = db.Column(db.String(200), nullable=True)
    # Human-readable description, e.g. "empty list edge case"

    # ── Ordering ─────────────────────────────────────────────────────────────
    order_index = db.Column(db.Integer, nullable=False, default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    challenge = db.relationship("Challenge", back_populates="test_cases")

    def __repr__(self) -> str:
        visibility = "hidden" if self.is_hidden else "visible"
        return (
            f"<TestCase challenge={self.challenge_id!r} "
            f"[{visibility}] in={self.input_args!r}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "challenge_id": self.challenge_id,
            "input_args": self.input_args,
            "expected_output": self.expected_output,
            "is_hidden": self.is_hidden,
            "label": self.label,
            "order_index": self.order_index,
            "created_at": self.created_at.isoformat(),
        }
