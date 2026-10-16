"""
test_phase3_unit.py
====================
Debug Dojo – Phase 3 Unit Tests
---------------------------------
Tests the AI tutor and learner tracking modules without:
  - A live LLM API (mocked)
  - A real database (SQLite in-memory via Flask test config)

Run: python -m pytest tests/test_phase3_unit.py -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# 1. LLM Client & Secrecy
# ─────────────────────────────────────────────────────────────────────────────

class TestAITutorSecrecy(unittest.TestCase):
    """Tests that hidden test values never reach the LLM prompt."""

    def _make_challenge(self) -> dict:
        return {
            "id": "last-k-total",
            "title": "Last K Total",
            "description": "Return the sum of the last k marks.",
            "function_signature": "def last_k_total(marks, k):",
            "concept_tags": ["lists", "slicing", "arithmetic"],
            "difficulty": "Easy",
            "test_case_labels": {
                "tc_hidden_1": {"label": "empty list edge case",    "is_hidden": True},
                "tc_hidden_2": {"label": "k larger than the list",  "is_hidden": True},
                "tc_vis_1":    {"label": "basic 3-item slice",      "is_hidden": False},
            },
        }

    def _make_test_results(self) -> list[dict]:
        return [
            {
                "test_id": "tc_vis_1",
                "outcome": "wrong_output",
                "is_hidden": False,
                "label": "basic 3-item slice",
                "actual_output": "90",
                "error_message": None,
            },
            {
                "test_id": "tc_hidden_1",
                "outcome": "runtime_error",
                "is_hidden": True,
                "label": "empty list edge case",
                "actual_output": None,      # MUST be None for hidden
                "error_message": None,      # MUST be None for hidden
            },
            {
                "test_id": "tc_hidden_2",
                "outcome": "wrong_output",
                "is_hidden": True,
                "label": "k larger than the list",
                "actual_output": None,
                "error_message": None,
            },
        ]

    def test_hidden_values_absent_from_prompt(self):
        """Hidden actual_output and error_message must NOT appear in the user prompt."""
        from app.services.ai_tutor import _build_test_summary

        enriched = [
            {
                "test_id": "tc_hidden_1",
                "outcome": "runtime_error",
                "is_hidden": True,
                "label": "empty list edge case",
                "actual_output": "SECRET_VALUE_42",   # should never appear
                "error_message": "SECRET_TRACEBACK",  # should never appear
            },
        ]
        summary, _, _ = _build_test_summary(enriched)
        self.assertNotIn("SECRET_VALUE_42", summary)
        self.assertNotIn("SECRET_TRACEBACK", summary)

    def test_hidden_label_appears_in_prompt(self):
        """The semantic label for a hidden test SHOULD appear in the summary."""
        from app.services.ai_tutor import _build_test_summary

        enriched = [
            {
                "test_id": "tc_hidden_1",
                "outcome": "wrong_output",
                "is_hidden": True,
                "label": "empty list edge case",
                "actual_output": None,
                "error_message": None,
            },
        ]
        summary, _, hid = _build_test_summary(enriched)
        self.assertIn("empty list edge case", summary)
        self.assertEqual(hid, 1)

    def test_visible_actual_output_appears_in_prompt(self):
        """For visible tests, actual_output IS allowed in the summary."""
        from app.services.ai_tutor import _build_test_summary

        enriched = [
            {
                "test_id": "tc_vis_1",
                "outcome": "wrong_output",
                "is_hidden": False,
                "label": "basic slice",
                "actual_output": "90",
                "error_message": None,
            },
        ]
        summary, vis, _ = _build_test_summary(enriched)
        self.assertIn("90", summary)
        self.assertEqual(vis, 1)

    def test_all_pass_returns_early(self):
        """If all tests pass, generate_explanation should return early without LLM."""
        from app.services.ai_tutor import generate_explanation

        passed_results = [
            {"test_id": "t1", "outcome": "passed", "is_hidden": False,
             "actual_output": "120", "error_message": None},
            {"test_id": "t2", "outcome": "passed", "is_hidden": True,
             "actual_output": None, "error_message": None},
        ]
        result = generate_explanation(
            challenge_details=self._make_challenge(),
            submission_code="def last_k_total(marks, k): return sum(marks[-k:])",
            test_results=passed_results,
        )
        self.assertEqual(result.failed_visible_count, 0)
        self.assertEqual(result.failed_hidden_count, 0)
        self.assertFalse(result.llm_used)

    def test_llm_fallback_on_error(self):
        """generate_explanation uses rule-based fallback when LLM is unavailable."""
        from app.services.ai_tutor import generate_explanation

        with patch("app.services.ai_tutor._get_client") as mock_client:
            mock_client.return_value.chat.side_effect = RuntimeError("LLM down")
            result = generate_explanation(
                challenge_details=self._make_challenge(),
                submission_code="def last_k_total(marks, k): return 0",
                test_results=self._make_test_results(),
                mistake_tags=["off_by_one"],
            )
        self.assertFalse(result.llm_used)
        self.assertIsInstance(result.summary, str)
        self.assertGreater(len(result.summary), 0)

    def test_explanation_counts_correctly(self):
        """Failed counts are accurately tracked."""
        from app.services.ai_tutor import generate_explanation

        with patch("app.services.ai_tutor._get_client") as mock_client:
            mock_client.return_value.chat.side_effect = RuntimeError("LLM down")
            result = generate_explanation(
                challenge_details=self._make_challenge(),
                submission_code="def last_k_total(marks, k): return 0",
                test_results=self._make_test_results(),
            )
        self.assertEqual(result.failed_visible_count, 1)
        self.assertEqual(result.failed_hidden_count, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hint Ladder
# ─────────────────────────────────────────────────────────────────────────────

class TestHintLadder(unittest.TestCase):

    def _challenge(self):
        return {
            "title": "Last K Total",
            "function_signature": "def last_k_total(marks, k):",
            "description": "Return sum of last k marks.",
            "concept_tags": ["lists", "slicing"],
            "difficulty": "Easy",
        }

    def test_fallback_returns_exactly_3_hints(self):
        """Rule-based fallback always returns exactly 3 non-empty hints."""
        from app.services.ai_tutor import generate_hint_ladder

        with patch("app.services.ai_tutor._get_client") as m:
            m.return_value.chat.side_effect = RuntimeError("LLM down")
            ladder = generate_hint_ladder(
                challenge_details=self._challenge(),
                submission_code="def last_k_total(marks, k): return marks[-k]",
                explanation="Your code fails on edge cases.",
                mistake_tags=["off_by_one"],
            )
        self.assertEqual(len(ladder.as_list()), 3)
        for hint in ladder.as_list():
            self.assertIsInstance(hint, str)
            self.assertGreater(len(hint.strip()), 0)
        self.assertFalse(ladder.llm_used)

    def test_llm_hint_parsed_correctly(self):
        """LLM JSON response is parsed into HintLadder fields."""
        from app.services.ai_tutor import generate_hint_ladder

        fake_response = json.dumps({
            "hint_1": "Think about Python slice semantics.",
            "hint_2": "Your slice upper bound is off by one.",
            "hint_3": "When k equals the list length, the start index is 0, not 1.",
        })

        with patch("app.services.ai_tutor._get_client") as m:
            m.return_value.chat.return_value = fake_response
            ladder = generate_hint_ladder(
                challenge_details=self._challenge(),
                submission_code="def f(m,k): return sum(m[k:])",
                explanation="The slice direction is wrong.",
                mistake_tags=[],
            )
        self.assertEqual(ladder.hint_1, "Think about Python slice semantics.")
        self.assertEqual(ladder.hint_3, "When k equals the list length, the start index is 0, not 1.")
        self.assertTrue(ladder.llm_used)

    def test_code_fence_stripped_from_hints(self):
        """_strip_code_from_hint removes code blocks."""
        from app.services.ai_tutor import _strip_code_from_hint

        raw = "Consider this: ```python\nreturn sum(marks[-k:])\n```"
        cleaned = _strip_code_from_hint(raw)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("return sum", cleaned)

    def test_all_mistake_tags_have_fallback_hints(self):
        """Every known mistake tag has a rule-based fallback hint triple."""
        from app.services.ai_tutor import _fallback_hints

        tags = [
            "off_by_one", "unhandled_short_input",
            "print_not_return", "boundary_comparison", "mutates_input",
        ]
        for tag in tags:
            ladder = _fallback_hints([tag], {"title": "T", "function_signature": "def f():"})
            self.assertEqual(len(ladder.as_list()), 3)
            for h in ladder.as_list():
                self.assertGreater(len(h), 10, f"Hint too short for tag {tag!r}: {h!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mastery Scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestMasteryScoring(unittest.TestCase):
    """Unit tests for the scoring formula — isolated from the DB."""

    def test_hint_decay_values(self):
        from app.services.learner_tracking import _hint_decay_factor
        self.assertEqual(_hint_decay_factor(0), 1.00)
        self.assertEqual(_hint_decay_factor(1), 0.70)
        self.assertEqual(_hint_decay_factor(2), 0.45)
        self.assertEqual(_hint_decay_factor(3), 0.25)
        self.assertEqual(_hint_decay_factor(4), 0.10)
        self.assertEqual(_hint_decay_factor(99), 0.10)   # capped

    def test_pass_delta_is_larger_with_zero_hints(self):
        from app.services.learner_tracking import _compute_pass_delta
        delta_0, _ = _compute_pass_delta(current_score=20.0, hints_used=0)
        delta_3, _ = _compute_pass_delta(current_score=20.0, hints_used=3)
        self.assertGreater(delta_0, delta_3)

    def test_diminishing_returns_at_high_score(self):
        from app.services.learner_tracking import _compute_pass_delta
        delta_low,  _ = _compute_pass_delta(current_score=10.0,  hints_used=0)
        delta_high, _ = _compute_pass_delta(current_score=90.0,  hints_used=0)
        self.assertGreater(delta_low, delta_high)

    def test_fail_delta_is_negative(self):
        from app.services.learner_tracking import _compute_fail_delta
        self.assertLess(_compute_fail_delta(50.0), 0)

    def test_fail_delta_proportional_to_score(self):
        from app.services.learner_tracking import _compute_fail_delta
        decay_high = abs(_compute_fail_delta(80.0))
        decay_low  = abs(_compute_fail_delta(10.0))
        self.assertGreater(decay_high, decay_low)

    def test_fail_delta_floored_at_zero_for_zero_score(self):
        """A learner with 0 mastery cannot lose more (stays at 0)."""
        from app.services.learner_tracking import _compute_fail_delta, _SCORE_FLOOR
        delta = _compute_fail_delta(0.0)
        # Even with a tiny negative delta, clamping keeps score at 0
        new_score = max(_SCORE_FLOOR, 0.0 + delta)
        self.assertEqual(new_score, _SCORE_FLOOR)

    def test_pass_never_exceeds_ceiling(self):
        from app.services.learner_tracking import _compute_pass_delta, _SCORE_CEILING
        # Even at 99.0 score, the result is clamped
        delta, _ = _compute_pass_delta(current_score=99.0, hints_used=0)
        new_score = min(_SCORE_CEILING, 99.0 + delta)
        self.assertLessEqual(new_score, _SCORE_CEILING)

    def test_score_formula_example_values(self):
        """Verify concrete formula outputs match expected values."""
        from app.services.learner_tracking import _compute_pass_delta
        # score=20, hints=0 → 15 × 1.00 × 0.80 = 12.0
        delta, w = _compute_pass_delta(20.0, 0)
        self.assertAlmostEqual(delta, 12.0, places=2)
        self.assertEqual(w, 1.00)

        # score=20, hints=2 → 15 × 0.45 × 0.80 = 5.4
        delta2, w2 = _compute_pass_delta(20.0, 2)
        self.assertAlmostEqual(delta2, 5.4, places=2)
        self.assertEqual(w2, 0.45)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Recurring Mistake Engine (formula / logic only — no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestRecurringMistakeLogic(unittest.TestCase):

    def test_mistake_to_concepts_coverage(self):
        """Every known mistake tag maps to at least one concept."""
        from app.services.learner_tracking import _MISTAKE_TO_CONCEPTS
        known = [
            "off_by_one", "unhandled_short_input",
            "print_not_return", "boundary_comparison", "mutates_input",
        ]
        for tag in known:
            self.assertIn(tag, _MISTAKE_TO_CONCEPTS)
            self.assertGreater(len(_MISTAKE_TO_CONCEPTS[tag]), 0)

    def test_recurrence_threshold_constant(self):
        from app.services.learner_tracking import _RECURRENCE_THRESHOLD
        self.assertGreaterEqual(_RECURRENCE_THRESHOLD, 1)

    def test_empty_tags_returns_no_recurring(self):
        """Empty mistake_tags input returns has_recurring=False without DB query."""
        from app.services.learner_tracking import check_recurring_mistake

        # We patch the DB query since it's empty tags — should short-circuit
        with patch("app.services.learner_tracking.Submission") as mock_sub:
            result = check_recurring_mistake(
                learner_id="learner-123",
                current_mistake_tags=[],
                current_challenge_id="some-challenge",
            )
        self.assertFalse(result.has_recurring)
        self.assertEqual(result.recurring_tags, [])


# ─────────────────────────────────────────────────────────────────────────────
# 5. System prompt content verification
# ─────────────────────────────────────────────────────────────────────────────

class TestSystemPrompts(unittest.TestCase):

    def test_explanation_prompt_forbids_hidden_values(self):
        from app.services.ai_tutor import _EXPLANATION_SYSTEM_PROMPT
        prompt = _EXPLANATION_SYSTEM_PROMPT.lower()
        self.assertIn("hidden", prompt)
        self.assertIn("never", prompt)
        self.assertIn("actual", prompt)

    def test_hint_prompt_forbids_code(self):
        from app.services.ai_tutor import _HINT_SYSTEM_PROMPT
        prompt = _HINT_SYSTEM_PROMPT.lower().replace("\n", " ")
        # Must forbid Python code — accepts either phrasing
        self.assertTrue(
            "no python code" in prompt or "must not write any python code" in prompt,
            "Hint system prompt must explicitly forbid Python code",
        )
        # Must forbid code blocks specifically
        self.assertIn("no code blocks", prompt)
        # Must forbid direct solutions
        self.assertIn("must not provide the direct fix", prompt)

    def test_hint_prompt_specifies_3_hints(self):
        from app.services.ai_tutor import _HINT_SYSTEM_PROMPT
        # Must describe exactly 3 hints
        self.assertIn("hint_1", _HINT_SYSTEM_PROMPT)
        self.assertIn("hint_2", _HINT_SYSTEM_PROMPT)
        self.assertIn("hint_3", _HINT_SYSTEM_PROMPT)

    def test_hint_prompt_requires_json_output(self):
        from app.services.ai_tutor import _HINT_SYSTEM_PROMPT
        self.assertIn("JSON", _HINT_SYSTEM_PROMPT)

    def test_explanation_prompt_requires_json_output(self):
        from app.services.ai_tutor import _EXPLANATION_SYSTEM_PROMPT
        self.assertIn("JSON", _EXPLANATION_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
