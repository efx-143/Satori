"""
seed_db.py
----------
Loads challenges.json into the database.
Run with: python seed_db.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.challenge import Challenge
from app.models.test_case import TestCase


def seed():
    app = create_app()
    seed_file = os.path.join(os.path.dirname(__file__), "seed", "challenges.json")

    with open(seed_file, "r", encoding="utf-8") as f:
        challenges_data = json.load(f)

    with app.app_context():
        inserted = 0
        skipped = 0

        for ch_data in challenges_data:
            challenge_id = ch_data["id"]

            if Challenge.query.get(challenge_id):
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

        db.session.commit()
        print(f"\nDone. Inserted={inserted}, Skipped={skipped}.")


if __name__ == "__main__":
    seed()
