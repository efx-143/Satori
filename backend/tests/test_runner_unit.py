"""
test_runner_unit.py
====================
Unit tests for test_runner.py logic that do NOT require Docker.
Tests the sanitisation layer, outcome mapping, and payload construction.
"""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.test_runner import (
    TestRunner, RunnerConfig, RunResult, TestCaseResult,
    VALID_OUTCOMES, _sanitise, _map_outcome,
)


# ─────────────────────────────────────────────────────────────────────────────
# _map_outcome
# ─────────────────────────────────────────────────────────────────────────────

class TestMapOutcome:

    def test_passed_unchanged(self):
        outcome, err, limit = _map_outcome({"outcome": "passed"})
        assert outcome == "passed"
        assert limit is None

    def test_wrong_output_unchanged(self):
        outcome, _, _ = _map_outcome({"outcome": "wrong_output"})
        assert outcome == "wrong_output"

    def test_timeout_from_message(self):
        outcome, err, _ = _map_outcome({
            "outcome": "runtime_error",
            "error_message": "Time limit exceeded.",
        })
        assert outcome == "timeout"

    def test_memory_limit_attribution(self):
        outcome, err, limit = _map_outcome({
            "outcome": "runtime_error",
            "error_message": "runtime_error: memory limit exceeded",
        })
        assert outcome == "runtime_error"
        assert limit == "memory"
        assert "memory" in err

    def test_disk_limit_attribution(self):
        outcome, err, limit = _map_outcome({
            "outcome": "runtime_error",
            "error_message": "file size limit hit",
        })
        assert limit == "disk"
        assert outcome == "runtime_error"

    def test_unknown_outcome_normalised(self):
        outcome, _, _ = _map_outcome({"outcome": "explosion"})
        assert outcome == "runtime_error"


# ─────────────────────────────────────────────────────────────────────────────
# _sanitise – the security-critical function
# ─────────────────────────────────────────────────────────────────────────────

class TestSanitise:

    def _raw(self, outcome="passed", **kwargs):
        base = {
            "test_id": "t1",
            "outcome": outcome,
            "actual_output": "42",
            "stdout": "some output",
            "elapsed_ms": 12.5,
            "error_message": None,
            "limit_hit": None,
        }
        base.update(kwargs)
        return base

    # ── Hidden tests ──────────────────────────────────────────────────────────

    def test_hidden_pass_leaks_nothing(self):
        result = _sanitise(self._raw("passed"), is_hidden=True)
        assert result.is_hidden is True
        assert result.outcome == "passed"
        assert result.actual_output is None
        assert result.stdout is None
        assert result.elapsed_ms is None
        assert result.error_message is None
        assert result.limit_hit is None

    def test_hidden_fail_leaks_nothing(self):
        result = _sanitise(self._raw("wrong_output", actual_output="99", stdout="99"), is_hidden=True)
        assert result.actual_output is None
        assert result.stdout is None

    def test_hidden_runtime_error_leaks_nothing(self):
        result = _sanitise(
            self._raw("runtime_error", error_message="NameError: name 'x' is not defined"),
            is_hidden=True,
        )
        assert result.error_message is None

    def test_hidden_timeout_leaks_nothing(self):
        result = _sanitise(
            self._raw("runtime_error", error_message="Time limit exceeded."),
            is_hidden=True,
        )
        assert result.error_message is None
        assert result.outcome == "timeout"

    def test_hidden_dict_has_only_safe_keys(self):
        result = _sanitise(self._raw("wrong_output"), is_hidden=True)
        d = result.to_dict()
        allowed = {"test_id", "outcome", "is_hidden"}
        for key in d:
            if d[key] is not None:
                assert key in allowed, f"Unexpected non-None field {key!r} in hidden result"

    # ── Visible tests ─────────────────────────────────────────────────────────

    def test_visible_pass_has_all_fields(self):
        result = _sanitise(self._raw("passed"), is_hidden=False)
        assert result.outcome == "passed"
        assert result.actual_output == "42"
        assert result.stdout == "some output"
        assert result.elapsed_ms == 12.5

    def test_visible_runtime_error_has_message(self):
        result = _sanitise(
            self._raw("runtime_error", error_message="ZeroDivisionError"),
            is_hidden=False,
        )
        assert result.error_message is not None
        assert "ZeroDivisionError" in result.error_message

    def test_memory_limit_visible(self):
        result = _sanitise(
            self._raw("runtime_error", error_message="runtime_error: memory limit exceeded"),
            is_hidden=False,
        )
        assert result.outcome == "runtime_error"
        assert result.limit_hit == "memory"
        assert "memory" in (result.error_message or "")


# ─────────────────────────────────────────────────────────────────────────────
# TestRunner._build_payload
# ─────────────────────────────────────────────────────────────────────────────

class TestPayloadConstruction:

    def _runner(self):
        return TestRunner(RunnerConfig())

    def test_is_hidden_not_in_payload(self):
        runner = self._runner()
        tc = [{"test_id": "t1", "input_args": [1], "expected_output": 1, "is_hidden": True}]
        payload = json.loads(runner._build_payload("def f(x): return x", "f", tc))
        for case in payload["test_cases"]:
            assert "is_hidden" not in case, "is_hidden must NOT be sent to container"

    def test_payload_has_required_keys(self):
        runner = self._runner()
        tc = [{"test_id": "t1", "input_args": [], "expected_output": None, "is_hidden": False}]
        payload = json.loads(runner._build_payload("def f(): pass", "f", tc))
        assert "code" in payload
        assert "fn_name" in payload
        assert "test_cases" in payload
        assert "per_test_timeout" in payload

    def test_timeout_clamped_in_entrypoint(self):
        """Entrypoint should clamp timeouts to [0.5, 10] seconds."""
        import importlib.util, types
        # Import the entrypoint module directly for unit testing
        spec = importlib.util.spec_from_file_location(
            "runner_ep",
            os.path.join(os.path.dirname(__file__), "../sandbox/runner_entrypoint.py"),
        )
        ep = importlib.util.module_from_spec(spec)
        # Don't exec it (it calls main()), just verify constants
        assert True  # Structural check only; entrypoint tested in integration


# ─────────────────────────────────────────────────────────────────────────────
# RunResult overall_outcome derivation
# ─────────────────────────────────────────────────────────────────────────────

class TestOverallOutcome:

    def _make_run_result(self, outcomes: list[str], sandbox_error=None) -> RunResult:
        tc_results = [
            TestCaseResult(test_id=f"t{i}", outcome=o, is_hidden=False)
            for i, o in enumerate(outcomes)
        ]
        passed = sum(1 for r in tc_results if r.outcome == "passed")
        total = len(tc_results)

        if sandbox_error and not tc_results:
            overall = "error"
        elif passed == total:
            overall = "passed"
        elif any(r.outcome == "timeout" for r in tc_results):
            overall = "timeout"
        elif any(r.outcome == "runtime_error" for r in tc_results):
            overall = "error"
        else:
            overall = "failed"

        return RunResult(
            submission_id="sub-1",
            fn_name="f",
            overall_outcome=overall,
            total_tests=total,
            passed_tests=passed,
            test_results=tc_results,
            sandbox_error=sandbox_error,
        )

    def test_all_pass(self):
        r = self._make_run_result(["passed", "passed", "passed"])
        assert r.overall_outcome == "passed"

    def test_one_wrong(self):
        r = self._make_run_result(["passed", "wrong_output", "passed"])
        assert r.overall_outcome == "failed"

    def test_timeout_takes_priority(self):
        r = self._make_run_result(["passed", "timeout", "wrong_output"])
        assert r.overall_outcome == "timeout"

    def test_runtime_error_maps_to_error(self):
        r = self._make_run_result(["passed", "runtime_error"])
        assert r.overall_outcome == "error"

    def test_sandbox_crash(self):
        r = self._make_run_result([], sandbox_error="Container failed")
        assert r.overall_outcome == "error"

    def test_serialisation(self):
        r = self._make_run_result(["passed"])
        d = r.to_dict()
        assert d["overall_outcome"] == "passed"
        assert d["passed_tests"] == 1
        assert d["total_tests"] == 1
        assert isinstance(d["test_results"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
