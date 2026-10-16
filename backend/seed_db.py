"""
seed_db.py
----------
Loads challenges.json into the database AND creates the demo learner.
Run with: python seed_db.py
Safe to re-run — skips rows that already exist.
"""
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.challenge import Challenge
from app.models.learner   import Learner
from app.models.test_case import TestCase

DEMO_LEARNER_ID = "00000000-0000-0000-0000-000000000001"


def seed_demo_learner():
    existing = db.session.get(Learner, DEMO_LEARNER_ID)
    if existing:
        print(f"  [skip]   demo learner already exists.")
        return
    learner = Learner(
        id=DEMO_LEARNER_ID,
        username="demo",
        email="demo@debugdojo.dev",
        password_hash="not-a-real-hash",
        display_name="Demo Learner",
        xp_points=350,
        streak_days=3,
    )
    db.session.add(learner)
    print(f"  [insert] demo learner  id={DEMO_LEARNER_ID}")


def seed_challenges():
    seed_file = os.path.join(os.path.dirname(__file__), "seed", "challenges.json")

    with open(seed_file, "r", encoding="utf-8") as f:
        challenges_data = json.load(f)

    inserted = 0
    skipped  = 0

    for ch_data in challenges_data:
        challenge_id = ch_data["id"]

        if db.session.get(Challenge, challenge_id):
            print(f"  [skip]   {challenge_id!r} already exists.")
            skipped += 1
            continue

        challenge = Challenge(
            id=challenge_id,
            title=ch_data["title"],
            description=ch_data["description"],
            difficulty=ch_data["difficulty"],
            concept_tags=ch_data["concept_tags"],
            function_signature=ch_data["function_signature"],
            starter_code=ch_data["starter_code"],
            xp_reward=ch_data.get("xp_reward", 10),
            time_limit_seconds=ch_data.get("time_limit_seconds", 5),
        )
        db.session.add(challenge)

        for idx, tc_data in enumerate(ch_data.get("test_cases", [])):
            tc = TestCase(
                challenge_id=challenge_id,
                input_args=tc_data["input_args"],
                expected_output=tc_data["expected_output"],
                is_hidden=tc_data.get("is_hidden", False),
                label=tc_data.get("label"),
                order_index=idx,
            )
            db.session.add(tc)

        print(f"  [insert] {challenge_id!r} with {len(ch_data['test_cases'])} test cases.")
        inserted += 1

    print(f"\n  Challenges: inserted={inserted}, skipped={skipped}.")


def seed():
    app = create_app()
    with app.app_context():
        print("\n=== Debug Dojo — Seeding database ===\n")
        print("[ Learner ]")
        seed_demo_learner()
        print("\n[ Challenges ]")
        seed_challenges()
        db.session.commit()
        print("\n✅  Done. Database is ready.\n")


if __name__ == "__main__":
    seed()
