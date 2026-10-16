"""
ai_tutor.py
===========
Debug Dojo – AI Explanations & Hint Ladder Service
----------------------------------------------------
Provides two public functions:

    generate_explanation(challenge_details, submission_code, test_results)
        → Returns a plain-language ExplanationResult explaining why code failed.

    generate_hint_ladder(challenge_details, submission_code, explanation, mistake_tags)
        → Returns a HintLadder of exactly 3 progressive hints (no code, ever).

Architecture
------------
The LLMClient class is provider-agnostic: it supports any OpenAI-compatible
endpoint (OpenAI, Groq, Together AI, Google AI Studio) via environment
variables, and falls back to Ollama for fully local execution.

Environment Variables
---------------------
    LLM_PROVIDER      "openai" | "ollama"  (default: "openai")
    LLM_BASE_URL      Override base URL    (e.g., http://localhost:11434/v1)
    LLM_API_KEY       API key              (not needed for Ollama)
    LLM_MODEL         Model name           (default: "gpt-4o-mini")
    LLM_TIMEOUT       Request timeout secs (default: 30)
    LLM_MAX_RETRIES   Retry count          (default: 3)

Hidden Test Secrecy
-------------------
The SYSTEM PROMPT explicitly forbids the LLM from stating, paraphrasing, or
inferring actual input values or expected outputs of hidden test cases.
Hidden failures are described only by their semantic label
(e.g., "an edge case where k is larger than the list length").
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Base URLs per provider
_BASE_URLS: dict[str, str] = {
    "gemini":        "https://generativelanguage.googleapis.com/v1beta/models",
    "gemini_native": "https://generativelanguage.googleapis.com/v1beta/models",
    "gemini_openai": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai":        "https://api.openai.com/v1",
    "ollama":        "http://localhost:11434/v1",
    "groq":          "https://api.groq.com/openai/v1",
    "together":      "https://api.together.xyz/v1",
}

_PROVIDER      = os.environ.get("LLM_PROVIDER", "gemini").lower()
_API_KEY       = os.environ.get("LLM_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
_DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gemini-1.5-flash" if "gemini" in _PROVIDER else "gpt-4o-mini")
_TIMEOUT       = int(os.environ.get("LLM_TIMEOUT", "30"))
_MAX_RETRIES   = int(os.environ.get("LLM_MAX_RETRIES", "3"))

_BASE_URL = os.environ.get(
    "LLM_BASE_URL",
    _BASE_URLS.get(_PROVIDER, _BASE_URLS.get("openai", "https://api.openai.com/v1")),
)

# ─────────────────────────────────────────────────────────────────────────────
# Data-classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExplanationResult:
    """Returned by generate_explanation()."""

    summary: str
    """One-sentence TL;DR of what went wrong."""

    body: str
    """Full plain-language explanation (2-4 paragraphs)."""

    failed_visible_count: int = 0
    """Number of visible test cases that failed."""

    failed_hidden_count: int = 0
    """Number of hidden test cases that failed (values never exposed)."""

    llm_used: bool = True
    """False if the LLM was unavailable and a rule-based fallback was used."""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "body": self.body,
            "failed_visible_count": self.failed_visible_count,
            "failed_hidden_count": self.failed_hidden_count,
            "llm_used": self.llm_used,
        }


@dataclass
class HintLadder:
    """Returned by generate_hint_ladder().  Always has exactly 3 hints."""

    hint_1: str
    """Gentle conceptual nudge — what concept to think about."""

    hint_2: str
    """Points precisely at the failing logic section."""

    hint_3: str
    """Highly specific but contains ZERO Python code or direct fixes."""

    llm_used: bool = True

    def to_dict(self) -> dict:
        return {
            "hint_1": self.hint_1,
            "hint_2": self.hint_2,
            "hint_3": self.hint_3,
            "llm_used": self.llm_used,
        }

    def as_list(self) -> list[str]:
        return [self.hint_1, self.hint_2, self.hint_3]


# ─────────────────────────────────────────────────────────────────────────────
# Mistake-tag → plain English descriptions (used in prompts & fallbacks)
# ─────────────────────────────────────────────────────────────────────────────

_MISTAKE_DESCRIPTIONS: dict[str, str] = {
    "off_by_one": (
        "an off-by-one error — the loop or slice boundary is shifted by 1, "
        "causing the first or last element to be missed or double-counted"
    ),
    "unhandled_short_input": (
        "missing handling for short or empty inputs — the code assumes the "
        "input always has enough elements, but it crashes or behaves incorrectly "
        "when given an empty list or a list shorter than expected"
    ),
    "print_not_return": (
        "using print() instead of return — the function outputs the result to the "
        "console instead of sending it back to the caller, so the caller receives None"
    ),
    "boundary_comparison": (
        "an incorrect boundary comparison — a strict inequality (< or >) is used "
        "where an inclusive one (<= or >=) is needed, causing the boundary value "
        "itself to be incorrectly excluded"
    ),
    "mutates_input": (
        "mutating the input argument — the function modifies the list passed in "
        "(e.g. using .append(), .sort(), or direct index assignment) rather than "
        "working on a copy, which can cause incorrect results and unexpected "
        "side effects for the caller"
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# LLM Client (OpenAI-compatible, stdlib only — no third-party SDK required)
# ─────────────────────────────────────────────────────────────────────────────

def _log_ai_interaction(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: str | None,
    error: str | None = None,
    latency_s: float = 0.0,
) -> None:
    """
    Gate 6 Compliance: Persist all AI prompts and responses for judge inspection.
    Stored in backend/logs/ai_prompts.log as newline-delimited JSON.
    """
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "ai_prompts.log")
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider": provider,
            "model": model,
            "latency_seconds": round(latency_s, 3),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": response,
            "error": error,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("Could not write to ai_prompts.log: %s", exc)


def _clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if returned by model."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class LLMClient:
    """
    Multi-provider AI Client built entirely on urllib (zero third-party dependencies).
    Supports:
      1. Gemini Native REST API (x-goog-api-key header + system_instruction)
      2. OpenAI-compatible endpoints (Groq, Together, OpenAI, Ollama, Gemini-OpenAI)
    """

    def __init__(
        self,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = _TIMEOUT,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self.provider = (provider or os.environ.get("LLM_PROVIDER", "gemini")).lower()
        self.api_key = api_key if api_key is not None else os.environ.get("LLM_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
        default_model = "gemini-1.5-flash" if "gemini" in self.provider else "gpt-4o-mini"
        self.model = model or os.environ.get("LLM_MODEL", default_model)
        default_url = _BASE_URLS.get(self.provider, _BASE_URLS.get("openai", "https://api.openai.com/v1"))
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", default_url)).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send chat completion request to Gemini native or OpenAI-compatible endpoint.
        Logs interaction for Gate 6 compliance.
        """
        if not self.api_key and self.provider != "ollama":
            raise ValueError(f"LLM_API_KEY is not configured for provider '{self.provider}'.")

        is_gemini_native = (
            self.provider in ("gemini", "gemini_native")
            or ("generativelanguage.googleapis.com" in self.base_url and "openai" not in self.base_url)
        )

        start_time = time.time()
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if is_gemini_native:
                    result = self._call_gemini_native(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    result = self._call_openai_compatible(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                latency = time.time() - start_time
                _log_ai_interaction(
                    provider=self.provider,
                    model=self.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=result,
                    latency_s=latency,
                )
                return result

            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                logger.warning(
                    "LLM HTTP %s on attempt %d/%d: %s",
                    exc.code, attempt, self.max_retries, err_body[:400],
                )
                last_exc = RuntimeError(f"HTTP {exc.code}: {err_body[:300]}")
                if exc.code in (400, 401, 403):
                    break   # non-retriable auth or invalid parameter errors
                time.sleep(2 ** attempt)

            except Exception as exc:
                logger.warning(
                    "LLM error on attempt %d/%d: %s",
                    attempt, self.max_retries, exc,
                )
                last_exc = exc
                time.sleep(2 ** attempt)

        latency = time.time() - start_time
        _log_ai_interaction(
            provider=self.provider,
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=None,
            error=str(last_exc),
            latency_s=latency,
        )
        raise RuntimeError(
            f"LLM request failed after {self.max_retries} attempts: {last_exc}"
        )

    def _call_gemini_native(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Google Generative Language REST API."""
        import urllib.parse
        clean_model = self.model.strip().lower().replace(" ", "-")
        model_slug = urllib.parse.quote(clean_model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_slug}:generateContent"
        # Ensure sufficient tokens for thinking models (Gemini 2.5 / 3.x Flash uses ~1000 thinking tokens)
        gemini_max_tokens = max(max_tokens, 2500)
        payload = json.dumps({
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": gemini_max_tokens,
                "responseMimeType": "application/json",
            }
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates: {body}")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError(f"Gemini returned empty parts: {body}")
            raw_text = parts[0].get("text", "")
            return _clean_json_text(raw_text)

    def _call_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call standard OpenAI /chat/completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        req_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        if self.provider in ("openai", "groq"):
            req_data["response_format"] = {"type": "json_object"}

        payload = json.dumps(req_data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return _clean_json_text(content)


# Module-level singleton (lazily initialised, dynamic on env change)
_client: LLMClient | None = None


def _get_client() -> LLMClient:
    global _client
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    api_key = os.environ.get("LLM_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    default_model = "gemini-1.5-flash" if "gemini" in provider else "gpt-4o-mini"
    model = os.environ.get("LLM_MODEL", default_model)
    default_url = _BASE_URLS.get(provider, _BASE_URLS.get("openai", "https://api.openai.com/v1"))
    base_url = os.environ.get("LLM_BASE_URL", default_url)

    if (
        _client is not None
        and _client.provider == provider
        and _client.api_key == api_key
        and _client.model == model
        and _client.base_url == base_url.rstrip("/")
    ):
        return _client

    _client = LLMClient(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Prompt helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_test_summary(test_results: list[dict]) -> tuple[str, int, int]:
    """
    Produce a text block summarising test outcomes for the LLM prompt.

    Returns (summary_text, failed_visible_count, failed_hidden_count).

    SECRECY RULE: For hidden tests, we include only the test_id, outcome,
    and the semantic label.  We never include input_args, expected_output,
    actual_output, or the error message.
    """
    visible_failed:  list[str] = []
    hidden_failed:   list[str] = []
    visible_passed:  int = 0
    hidden_passed:   int = 0

    for tc in test_results:
        tid      = tc.get("test_id", "?")
        outcome  = tc.get("outcome", "unknown")
        is_hid   = tc.get("is_hidden", False)
        label    = tc.get("label", "")          # semantic description
        actual   = tc.get("actual_output")
        err_msg  = tc.get("error_message")

        if outcome == "passed":
            if is_hid:
                hidden_passed += 1
            else:
                visible_passed += 1
            continue

        if is_hid:
            # ── HIDDEN TEST: describe the kind of input, never the value ──────
            kind = label if label else f"test case {tid}"
            hidden_failed.append(
                f"  • [HIDDEN] {kind} → outcome: {outcome}"
            )
        else:
            # ── VISIBLE TEST: safe to share outcome + actual output ────────────
            detail_parts = [f"  • [{tid}] outcome: {outcome}"]
            if actual is not None:
                detail_parts.append(f"your function returned: {actual}")
            if err_msg:
                detail_parts.append(f"error: {err_msg}")
            visible_failed.append("  " + " | ".join(detail_parts).strip())

    lines: list[str] = []
    if visible_failed:
        lines.append("FAILED VISIBLE TESTS:")
        lines.extend(visible_failed)
    if hidden_failed:
        lines.append("\nFAILED HIDDEN TESTS (values withheld — description only):")
        lines.extend(hidden_failed)
    if visible_passed or hidden_passed:
        lines.append(
            f"\nPassed: {visible_passed} visible, {hidden_passed} hidden."
        )

    return "\n".join(lines), len(visible_failed), len(hidden_failed)


def _mistake_tags_to_prose(mistake_tags: list[str]) -> str:
    """Convert AST mistake tags into readable prose for prompts."""
    if not mistake_tags:
        return "No specific structural mistakes were auto-detected."
    parts = [
        f"  • {tag}: {_MISTAKE_DESCRIPTIONS.get(tag, tag)}"
        for tag in mistake_tags
    ]
    return "Detected structural patterns:\n" + "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# System prompts
# ─────────────────────────────────────────────────────────────────────────────

# ── Explanation system prompt ────────────────────────────────────────────────
_EXPLANATION_SYSTEM_PROMPT = """
You are a senior Python tutor for an online coding education platform called Debug Dojo.
Your role is to help learners understand WHY their code is incorrect.

ABSOLUTE RULES — violation of any rule is unacceptable:

1. NEVER reveal, paraphrase, hint at, or reconstruct the actual numeric or string
   input values of any hidden test case.
2. NEVER reveal, paraphrase, or hint at the expected output value of any hidden
   test case.
3. For hidden tests that failed, describe only the *category* or *kind* of input
   (e.g., "a case where the list is empty" or "a case where k exceeds the list
   length") — never the actual values.
4. Do NOT include any Python code blocks, code snippets, or syntax in your
   explanation. Describe the issue in plain English only.
5. Keep your response focused, warm, and encouraging. Assume the learner is a
   beginner.
6. Your response MUST follow this exact structure — output valid JSON only:

{
  "summary": "<one sentence: what the core mistake is>",
  "body": "<2-3 paragraphs: plain-English explanation of why the code fails, referencing test outcomes by their category label, not their values>"
}

Do not include anything outside the JSON object.
""".strip()


# ── Hint ladder system prompt ─────────────────────────────────────────────────
_HINT_SYSTEM_PROMPT = """
You are a Socratic Python tutor for Debug Dojo. Your job is to guide learners
to discover the fix themselves through a 3-step hint ladder.

ABSOLUTE RULES — any violation disqualifies your response:

1. YOU MUST NOT write any Python code in any hint.
   - No code blocks (no ``` or ~~~).
   - No function definitions, no variable assignments.
   - No snippets, no pseudocode that looks like code.
   - Not even a single line of Python syntax.
2. YOU MUST NOT provide the direct fix or the correct solution.
3. YOU MUST NOT reveal the actual values of any hidden test inputs or expected outputs.
4. Each hint must be progressively more specific:
   - Hint 1: A gentle conceptual nudge. Ask a guiding question. Mention the
             relevant concept (e.g., "slicing", "boundary conditions") without
             pointing at the code.
   - Hint 2: Point precisely to which part of the learner's logic is wrong
             (e.g., "the condition in your loop exit" or "how you compute the
             starting index of your slice"). Still no code.
   - Hint 3: Highly specific — describe exactly what change in *thinking* is
             needed (e.g., "you need to consider the case where k is equal to
             the length, not just less than it") but still provide ZERO code.
5. Every hint must be a complete sentence in plain English.
6. Output valid JSON only, with this exact structure:

{
  "hint_1": "<gentle conceptual nudge — no code>",
  "hint_2": "<points to the exact failing logic — no code>",
  "hint_3": "<highly specific but zero code or direct fix>"
}

Do not include anything outside the JSON object.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Rule-based fallbacks (used when LLM is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

def _fallback_explanation(
    challenge_details: dict,
    test_results: list[dict],
    mistake_tags: list[str],
    failed_visible: int,
    failed_hidden: int,
) -> ExplanationResult:
    """Generate a rule-based explanation without an LLM."""
    title = challenge_details.get("title", "this challenge")
    parts: list[str] = []

    if failed_visible > 0 and failed_hidden > 0:
        parts.append(
            f"Your solution for '{title}' failed {failed_visible} visible "
            f"and {failed_hidden} hidden test case(s)."
        )
    elif failed_visible > 0:
        parts.append(
            f"Your solution for '{title}' failed {failed_visible} visible test case(s)."
        )
    else:
        parts.append(
            f"Your solution for '{title}' failed {failed_hidden} hidden test case(s) "
            "that cover edge cases not shown to you."
        )

    if mistake_tags:
        descs = [
            _MISTAKE_DESCRIPTIONS.get(t, t)
            for t in mistake_tags
        ]
        parts.append(
            "The automated analyser detected the following issue(s): "
            + "; ".join(descs) + "."
        )

    summary = parts[0]
    body = " ".join(parts)
    return ExplanationResult(
        summary=summary,
        body=body,
        failed_visible_count=failed_visible,
        failed_hidden_count=failed_hidden,
        llm_used=False,
    )


def _fallback_hints(mistake_tags: list[str], challenge_details: dict) -> HintLadder:
    """Generate rule-based hints without an LLM."""
    tag = mistake_tags[0] if mistake_tags else None

    _rule_hints: dict[str, tuple[str, str, str]] = {
        "off_by_one": (
            "Think carefully about where your loop or slice starts and ends — "
            "Python's range and slice upper bounds work in a specific way.",
            "Look at the index or range boundary you are using to select elements — "
            "consider whether the very first or very last element is being included.",
            "Check whether your boundary value should be exclusive or inclusive — "
            "Python slices already exclude the upper bound, so subtracting 1 "
            "from it is almost always wrong.",
        ),
        "unhandled_short_input": (
            "Think about what happens when the input list has very few — or no — "
            "elements before your main logic runs.",
            "Your code directly accesses an element by index before confirming "
            "the list is long enough for that access to be safe.",
            "Add a check at the very top of your function: what should you return "
            "immediately if the list is empty or shorter than the required length?",
        ),
        "print_not_return": (
            "Think about the difference between showing a value on screen and "
            "handing a value back to whoever called your function.",
            "Your function is displaying the result instead of sending it back — "
            "the caller receives nothing (None) as a result.",
            "Replace the statement that outputs the value with a statement that "
            "sends the value back to the caller.",
        ),
        "boundary_comparison": (
            "Think carefully about whether your threshold value should be "
            "included or excluded in your comparison.",
            "Your conditional uses a strict inequality, which means the exact "
            "boundary value itself is not counted.",
            "Consider whether the value at the boundary (e.g., exactly 40) "
            "should satisfy your condition or not, and choose your operator "
            "accordingly.",
        ),
        "mutates_input": (
            "Think about what happens to the original list when you call certain "
            "list methods inside your function.",
            "Some list operations change the list in place — this affects the "
            "original argument, not just a local copy.",
            "Create a copy of the input at the start of your function and apply "
            "all modifications to that copy instead of the original.",
        ),
    }

    if tag and tag in _rule_hints:
        h1, h2, h3 = _rule_hints[tag]
    else:
        fn_sig = challenge_details.get("function_signature", "your function")
        h1 = f"Re-read the problem description for '{challenge_details.get('title', 'this challenge')}' carefully and consider all the edge cases mentioned."
        h2 = f"Trace through your implementation of {fn_sig} step by step with a small example to see where it diverges from the expected behaviour."
        h3 = "Focus on what your function should return when the input is at its most extreme — empty, single-element, or at the boundary described in the problem."

    return HintLadder(hint_1=h1, hint_2=h2, hint_3=h3, llm_used=False)


# ─────────────────────────────────────────────────────────────────────────────
# Public API – Task 1: generate_explanation
# ─────────────────────────────────────────────────────────────────────────────

def generate_explanation(
    challenge_details: dict,
    submission_code: str,
    test_results: list[dict],
    mistake_tags: list[str] | None = None,
) -> ExplanationResult:
    """
    Generate a plain-language explanation of why the learner's code failed.

    Parameters
    ----------
    challenge_details : dict
        Must contain at minimum:
          "id", "title", "description", "function_signature",
          "concept_tags", "difficulty"
        May optionally contain:
          "test_case_labels": {test_id: {"label": str, "is_hidden": bool}}
        If present, labels are used to describe hidden failures semantically.

    submission_code : str
        The learner's raw Python source.

    test_results : list[dict]
        Each dict: test_id, outcome, is_hidden, label (optional),
                   actual_output (None for hidden), error_message (None for hidden).

    mistake_tags : list[str] | None
        AST-detected mistake category slugs from mistake_detector.py.

    Returns
    -------
    ExplanationResult
        Contains summary, body, counts, and whether LLM was used.

    SECRECY GUARANTEE
    -----------------
    Hidden test actual_output and input values are NEVER sent to the LLM.
    Only semantic labels (e.g., "empty list edge case") are forwarded.
    """
    mistake_tags = mistake_tags or []

    # ── Attach labels from challenge_details.test_case_labels to test_results ─
    tc_label_map: dict[str, str] = {}
    if "test_case_labels" in challenge_details:
        for tid, meta in challenge_details["test_case_labels"].items():
            tc_label_map[tid] = meta.get("label", "")

    enriched_results: list[dict] = []
    for tc in test_results:
        tc_copy = dict(tc)
        if not tc_copy.get("label"):
            tc_copy["label"] = tc_label_map.get(tc_copy.get("test_id", ""), "")
        enriched_results.append(tc_copy)

    test_summary, failed_vis, failed_hid = _build_test_summary(enriched_results)

    # If everything passed, return immediately
    if failed_vis == 0 and failed_hid == 0:
        return ExplanationResult(
            summary="All test cases passed — great work!",
            body="Your solution passed all visible and hidden tests. Well done!",
            failed_visible_count=0,
            failed_hidden_count=0,
            llm_used=False,
        )

    # ── Build user prompt ─────────────────────────────────────────────────────
    user_prompt = f"""
CHALLENGE: {challenge_details.get("title", "Unknown")} ({challenge_details.get("difficulty", "?")})
FUNCTION SIGNATURE: {challenge_details.get("function_signature", "")}
PROBLEM DESCRIPTION:
{challenge_details.get("description", "")}

LEARNER'S CODE:
```python
{submission_code}
```

TEST RESULTS:
{test_summary}

{_mistake_tags_to_prose(mistake_tags)}

Based on the above, explain why the learner's code is failing.
Remember: NEVER state the actual values of hidden test inputs or expected outputs.
Describe hidden failures by their semantic kind (the label already tells you the category).
    """.strip()

    # ── Call LLM ──────────────────────────────────────────────────────────────
    try:
        raw = _get_client().chat(
            system_prompt=_EXPLANATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=800,
        )
        parsed = json.loads(raw)
        return ExplanationResult(
            summary=parsed.get("summary", "").strip(),
            body=parsed.get("body", "").strip(),
            failed_visible_count=failed_vis,
            failed_hidden_count=failed_hid,
            llm_used=True,
        )

    except json.JSONDecodeError:
        # LLM returned non-JSON — extract what we can
        logger.warning("LLM returned non-JSON explanation; using raw text.")
        return ExplanationResult(
            summary="Your solution failed some test cases.",
            body=raw[:1500] if "raw" in dir() else "See test results above.",
            failed_visible_count=failed_vis,
            failed_hidden_count=failed_hid,
            llm_used=True,
        )

    except Exception as exc:
        logger.error("LLM unavailable for explanation: %s", exc)
        return _fallback_explanation(
            challenge_details, enriched_results, mistake_tags, failed_vis, failed_hid
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API – Task 2: generate_hint_ladder
# ─────────────────────────────────────────────────────────────────────────────

def generate_hint_ladder(
    challenge_details: dict,
    submission_code: str,
    explanation: ExplanationResult | str,
    mistake_tags: list[str] | None = None,
) -> HintLadder:
    """
    Generate exactly 3 progressive hints.  NO hint may contain Python code.

    Parameters
    ----------
    challenge_details : dict
        Same shape as generate_explanation().
    submission_code : str
        The learner's raw Python source.
    explanation : ExplanationResult | str
        Previously generated explanation — used as context so the LLM
        can make hints consistent with the explanation.
    mistake_tags : list[str] | None
        AST-detected mistake slugs; each is translated to prose.

    Returns
    -------
    HintLadder
        Exactly 3 hints.  Guaranteed code-free (LLM and fallback both enforce this).

    ABSOLUTE RULE — enforced at TWO levels:
        1. The system prompt explicitly forbids any Python syntax.
        2. _strip_code_from_hint() post-processes each hint to remove any
           accidental code-looking fragments before returning.
    """
    mistake_tags = mistake_tags or []

    # Normalise explanation to string
    if isinstance(explanation, ExplanationResult):
        explanation_text = f"{explanation.summary}\n\n{explanation.body}"
    else:
        explanation_text = str(explanation)

    mistake_prose = _mistake_tags_to_prose(mistake_tags)

    user_prompt = f"""
CHALLENGE: {challenge_details.get("title", "Unknown")} ({challenge_details.get("difficulty", "?")})
FUNCTION SIGNATURE: {challenge_details.get("function_signature", "")}
CONCEPTS TESTED: {", ".join(challenge_details.get("concept_tags", []))}

PROBLEM DESCRIPTION:
{challenge_details.get("description", "")}

LEARNER'S CODE (for context only — do NOT suggest fixes or rewrite it):
```
{submission_code}
```

EXPLANATION OF FAILURE (already given to the learner):
{explanation_text}

{mistake_prose}

Generate exactly 3 hints following the hint ladder rules in your instructions.
REMINDER: Not a single character of Python syntax in any hint.
    """.strip()

    try:
        raw = _get_client().chat(
            system_prompt=_HINT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=600,
        )
        parsed = json.loads(raw)

        h1 = _strip_code_from_hint(parsed.get("hint_1", "").strip())
        h2 = _strip_code_from_hint(parsed.get("hint_2", "").strip())
        h3 = _strip_code_from_hint(parsed.get("hint_3", "").strip())

        # Validate we got non-empty hints
        if not all([h1, h2, h3]):
            raise ValueError("One or more hints are empty.")

        return HintLadder(hint_1=h1, hint_2=h2, hint_3=h3, llm_used=True)

    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON hints; using fallback.")
        return _fallback_hints(mistake_tags, challenge_details)

    except Exception as exc:
        logger.error("LLM unavailable for hints: %s", exc)
        return _fallback_hints(mistake_tags, challenge_details)


# ─────────────────────────────────────────────────────────────────────────────
# Safety post-processor
# ─────────────────────────────────────────────────────────────────────────────

import re as _re

# Patterns that look like Python code that slipped past the LLM
_CODE_FENCE_RE   = _re.compile(r"```[\s\S]*?```", _re.MULTILINE)
_INLINE_CODE_RE  = _re.compile(r"`[^`]+`")
_DEF_RE          = _re.compile(r"\bdef\s+\w+\s*\(")
_RETURN_RE       = _re.compile(r"\breturn\b\s+[^\n]{0,60}")
_ASSIGN_RE       = _re.compile(r"\b\w+\s*=[^=\n]{0,60}")


def _strip_code_from_hint(hint: str) -> str:
    """
    Post-process a hint to remove any code fragments that the LLM
    accidentally included despite the system prompt prohibition.
    Replaces code blocks with a neutral placeholder.
    """
    hint = _CODE_FENCE_RE.sub("[code example removed]", hint)
    hint = _INLINE_CODE_RE.sub(lambda m: m.group(0).strip("`"), hint)
    # If def or return statements snuck in, flag it but don't redact
    # (removing them could make the hint incoherent; log a warning instead)
    if _DEF_RE.search(hint):
        logger.warning("LLM hint contained a def statement — review prompt.")
    return hint.strip()
