"""
Challenge model – stores problem data.
"""
import datetime
import uuid

from sqlalchemy.dialects.sqlite import JSON  # falls back gracefully on other DBs

from app import db


class Challenge(db.Model):
    __tablename__ = "challenges"

    # ── Primary key ──────────────────────────────────────────────────────────
    id = db.Column(db.String(80), primary_key=True)
    # Human-readable slug, e.g. "last-k-total".  Doubles as the unique key
    # so seeds are idempotent.

    # ── Metadata ─────────────────────────────────────────────────────────────
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(
        db.Enum("Easy", "Medium", "Hard", name="difficulty_enum"),
        nullable=False,
        index=True,
    )

    # ── Code scaffold ────────────────────────────────────────────────────────
    starter_code = db.Column(db.Text, nullable=False)
    function_signature = db.Column(db.String(200), nullable=False)
    # e.g. "def last_k_total(marks, k):"

    # ── Concept classification ────────────────────────────────────────────────
    # Stored as a JSON array of strings, e.g. ["lists", "loops"]
    concept_tags = db.Column(JSON, nullable=False, default=list)

    # ── Leaderboard / UX hints ────────────────────────────────────────────────
    xp_reward = db.Column(db.Integer, nullable=False, default=10)
    time_limit_seconds = db.Column(db.Integer, nullable=False, default=5)
    is_published = db.Column(db.Boolean, nullable=False, default=True)

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

    # ── Relationships ─────────────────────────────────────────────────────────
    test_cases = db.relationship(
        "TestCase", back_populates="challenge", cascade="all, delete-orphan"
    )
    submissions = db.relationship(
        "Submission", back_populates="challenge", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Challenge {self.id!r} [{self.difficulty}]>"

    def to_dict(self, include_hidden_tests: bool = False) -> dict:
        visible_tests = [
            tc.to_dict() for tc in self.test_cases if not tc.is_hidden
        ]
        hidden_tests = (
            [tc.to_dict() for tc in self.test_cases if tc.is_hidden]
            if include_hidden_tests
            else []
        )
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "starter_code": self.starter_code,
            "function_signature": self.function_signature,
            "concept_tags": self.concept_tags,
            "xp_reward": self.xp_reward,
            "time_limit_seconds": self.time_limit_seconds,
            "is_published": self.is_published,
            "visible_test_cases": visible_tests,
            **({"hidden_test_cases": hidden_tests} if include_hidden_tests else {}),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
