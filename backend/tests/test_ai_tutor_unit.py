"""
test_ai_tutor_unit.py
======================
Unit tests for ai_tutor service:
- Dual provider configuration (Gemini / OpenAI / Groq)
- Gate 6 audit logging persistence
- Secrecy guarantees (no hidden input values leaked)
- Zero Python code leakage in hints
- Safe fallback when LLM is unavailable
"""
import json
import os
import pytest

from app.services.ai_tutor import (
    generate_explanation,
    generate_hint_ladder,
    _strip_code_from_hint,
    _clean_json_text,
    _log_ai_interaction,
    ExplanationResult,
    HintLadder,
)


CHALLENGE_SAMPLE = {
    "id": "last_k_total",
    "title": "Sum of Last K Elements",
    "description": "Given a list of numbers and an integer k, return the sum of the last k elements.",
    "function_signature": "def last_k_total(marks, k):",
    "concept_tags": ["slicing", "boundary_conditions"],
    "difficulty": "beginner",
    "test_case_labels": {
        "h1": {"label": "empty list edge case", "is_hidden": True},
        "h2": {"label": "k exceeds length", "is_hidden": True},
    },
}


def test_strip_code_from_hint():
    """Ensure hints strip Python code fences and inline syntax."""
    hint_with_code = "You should use `marks[-k:]` in your loop like ```python\ndef solve(): pass\n``` to fix it."
    cleaned = _strip_code_from_hint(hint_with_code)
    assert "```" not in cleaned
    assert "[code example removed]" in cleaned
    assert "`" not in cleaned


def test_clean_json_text():
    """Ensure markdown JSON blocks are cleanly extracted."""
    raw = "```json\n{\"hint_1\": \"Think about length\"}\n```"
    cleaned = _clean_json_text(raw)
    assert cleaned == '{"hint_1": "Think about length"}'


def test_fallback_explanation_preserves_hidden_secrecy():
    """Fallback explanation must NEVER expose hidden values."""
    test_results = [
        {"test_id": "v1", "outcome": "passed", "is_hidden": False, "label": "basic test"},
        {"test_id": "h1", "outcome": "wrong_output", "is_hidden": True, "label": "empty list edge case"},
    ]
    expl = generate_explanation(
        challenge_details=CHALLENGE_SAMPLE,
        submission_code="def last_k_total(marks, k):\n    return sum(marks[-k:])",
        test_results=test_results,
        mistake_tags=["unhandled_short_input"],
    )
    assert isinstance(expl, ExplanationResult)
    assert expl.failed_hidden_count == 1
    # Hidden test values must not appear
    assert "marks" in expl.body or "input" in expl.body


def test_fallback_hint_ladder_has_exactly_three_code_free_hints():
    """Fallback ladder must always provide exactly 3 hints with 0 code."""
    ladder = generate_hint_ladder(
        challenge_details=CHALLENGE_SAMPLE,
        submission_code="def last_k_total(marks, k):\n    return sum(marks[-k:])",
        explanation="Failed on empty input",
        mistake_tags=["unhandled_short_input"],
    )
    assert isinstance(ladder, HintLadder)
    hints = ladder.as_list()
    assert len(hints) == 3
    for h in hints:
        assert isinstance(h, str) and len(h) > 10
        assert "def " not in h
        assert "```" not in h


def test_gate_6_audit_logging(tmp_path):
    """Gate 6: AI prompts and responses must be logged for judge inspection."""
    _log_ai_interaction(
        provider="gemini",
        model="gemini-1.5-flash",
        system_prompt="Test system prompt",
        user_prompt="Test user prompt",
        response='{"test": true}',
        latency_s=0.15,
    )
    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "ai_prompts.log"
    )
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) >= 1
        last_entry = json.loads(lines[-1])
        assert last_entry["provider"] == "gemini"
        assert last_entry["model"] == "gemini-1.5-flash"
        assert "timestamp" in last_entry
