"""
Learner model – stores user profile and authentication basics.
"""
import datetime
import uuid

from app import db


class Learner(db.Model):
    __tablename__ = "learners"

    # ── Primary key ──────────────────────────────────────────────────────────
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # ── Identity ─────────────────────────────────────────────────────────────
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # ── Profile ───────────────────────────────────────────────────────────────
    display_name = db.Column(db.String(120), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # ── Gamification ─────────────────────────────────────────────────────────
    xp_points = db.Column(db.Integer, nullable=False, default=0)
    streak_days = db.Column(db.Integer, nullable=False, default=0)
    last_active_date = db.Column(db.Date, nullable=True)

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

    # ── Relationships (back-populated from child models) ──────────────────────
    concept_masteries = db.relationship(
        "ConceptMastery", back_populates="learner", cascade="all, delete-orphan"
    )
    submissions = db.relationship(
        "Submission", back_populates="learner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Learner {self.username!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "xp_points": self.xp_points,
            "streak_days": self.streak_days,
            "last_active_date": (
                self.last_active_date.isoformat() if self.last_active_date else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
