"""
test_sandbox_redteam.py
========================
Debug Dojo – Sandbox Red-Team Test Suite
-----------------------------------------
Verifies every security constraint listed in the Phase 2 brief.

Run with:
    cd backend
    python -m pytest tests/test_sandbox_redteam.py -v

Each test submits deliberately malicious learner code to the live sandbox
and asserts that the runner correctly blocks or contains it.
"""

from __future__ import annotations

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.test_runner import TestRunner, RunnerConfig

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def runner() -> TestRunner:
    """Shared runner with tight limits for red-team testing."""
    return TestRunner(RunnerConfig(
        memory_mb=64,
        cpu_fraction=0.5,
        pids_limit=32,
        per_test_timeout_s=4.0,
        container_timeout_s=20.0,
    ))


def _tc(test_id: str, args: list, expected, *, hidden: bool = False) -> dict:
    return {
        "test_id": test_id,
        "input_args": args,
        "expected_output": expected,
        "is_hidden": hidden,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Network access – must be blocked
# ─────────────────────────────────────────────────────────────────────────────

class TestNetworkIsolation:

    def test_socket_import_blocked(self, runner):
        """Learner code that tries to import socket should get runtime_error."""
        code = """
def solution(x):
    import socket
    s = socket.socket()
    s.connect(("8.8.8.8", 53))
    return "exfiltrated"
"""
        result = runner.run(code, "solution", [_tc("net1", [1], "exfiltrated")])
        tc = result.test_results[0]
        assert tc.outcome == "runtime_error", (
            f"Expected runtime_error (import blocked), got {tc.outcome!r}"
        )

    def test_urllib_blocked(self, runner):
        """urllib.request must be blocked by the import hook."""
        code = """
def solution(x):
    import urllib.request
    return urllib.request.urlopen("http://example.com").read()
"""
        result = runner.run(code, "solution", [_tc("net2", [1], "data")])
        assert result.test_results[0].outcome == "runtime_error"

    def test_http_blocked(self, runner):
        code = """
def solution(x):
    import http.client
    conn = http.client.HTTPConnection("example.com")
    conn.request("GET", "/")
    return conn.getresponse().read()
"""
        result = runner.run(code, "solution", [_tc("net3", [1], "data")])
        assert result.test_results[0].outcome == "runtime_error"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Filesystem – sensitive paths must be unreadable
# ─────────────────────────────────────────────────────────────────────────────

class TestFilesystemIsolation:

    def test_cannot_read_etc_passwd(self, runner):
        code = """
def solution(x):
    with open("/etc/passwd") as f:
        return f.read()
"""
        result = runner.run(code, "solution", [_tc("fs1", [1], "root")])
        assert result.test_results[0].outcome == "runtime_error"

    def test_cannot_read_env_secrets(self, runner):
        """Learner should not be able to read /proc/1/environ or host env."""
        code = """
def solution(x):
    import os
    return os.environ.get("SECRET_KEY", "none")
"""
        result = runner.run(code, "solution", [_tc("fs2", [1], "SUPERSECRET")])
        # Either blocked by import hook or returns wrong_output
        assert result.test_results[0].outcome in ("runtime_error", "wrong_output")

    def test_cannot_write_to_root_fs(self, runner):
        """Read-only flag must prevent writes to /tmp in root fs."""
        code = """
def solution(x):
    with open("/evil.txt", "w") as f:
        f.write("pwned")
    return "wrote"
"""
        result = runner.run(code, "solution", [_tc("fs3", [1], "wrote")])
        assert result.test_results[0].outcome == "runtime_error"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Compute – infinite loops must timeout
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeLimits:

    def test_infinite_loop_times_out(self, runner):
        code = """
def solution(x):
    while True:
        pass
"""
        result = runner.run(code, "solution", [_tc("cpu1", [1], 42)])
        assert result.test_results[0].outcome == "timeout", (
            f"Infinite loop must time out, got {result.test_results[0].outcome!r}"
        )

    def test_fork_bomb_blocked(self, runner):
        """os.fork() or subprocess.Popen should be blocked."""
        code = """
def solution(x):
    import os
    for _ in range(200):
        os.fork()
    return "forked"
"""
        result = runner.run(code, "solution", [_tc("fork1", [1], "forked")])
        assert result.test_results[0].outcome == "runtime_error"

    def test_memory_bomb_caught(self, runner):
        """Allocating huge list must hit memory limit → runtime_error."""
        code = """
def solution(x):
    # Attempt to allocate ~512 MiB
    return [0] * (512 * 1024 * 1024 // 8)
"""
        result = runner.run(code, "solution", [_tc("mem1", [1], None)])
        assert result.test_results[0].outcome in ("runtime_error", "timeout"), (
            "Memory bomb must result in runtime_error or timeout"
        )

    def test_recursion_bomb_caught(self, runner):
        code = """
def solution(x):
    return solution(x + 1)
"""
        result = runner.run(code, "solution", [_tc("rec1", [0], None)])
        assert result.test_results[0].outcome == "runtime_error"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Hidden test secrecy – no leakage under any circumstances
# ─────────────────────────────────────────────────────────────────────────────

class TestHiddenTestSecrecy:

    def test_hidden_fail_reveals_nothing(self, runner):
        """A failing hidden test must only expose test_id + outcome."""
        code = """
def solution(x):
    return x * 2   # wrong intentionally
"""
        test_cases = [_tc("h1", [21], 42, hidden=True)]
        result = runner.run(code, "solution", test_cases)
        tc = result.test_results[0]

        assert tc.is_hidden is True
        assert tc.test_id == "h1"
        assert tc.outcome in ("passed", "wrong_output", "runtime_error", "timeout")

        assert tc.actual_output is None,   "actual_output must be None for hidden"
        assert tc.stdout is None,          "stdout must be None for hidden"
        assert tc.elapsed_ms is None,      "elapsed_ms must be None for hidden"
        assert tc.error_message is None,   "error_message must be None for hidden"
        assert tc.limit_hit is None,       "limit_hit must be None for hidden"

    def test_print_cannot_leak_hidden_input(self, runner):
        """
        Learner code that prints() the arguments should NOT have that output
        surfaced when the test is hidden.
        """
        code = """
def solution(x):
    print("THE SECRET INPUT IS:", x)
    return x + 1
"""
        test_cases = [_tc("h2", [99], 100, hidden=True)]
        result = runner.run(code, "solution", test_cases)
        tc = result.test_results[0]

        assert tc.stdout is None, "stdout must NEVER be revealed for hidden tests"
        # Ensure the secret value doesn't appear anywhere in the serialised dict
        serialised = str(tc.to_dict())
        assert "99" not in serialised or tc.outcome == "passed", (
            "Hidden input value must not appear in the result payload"
        )

    def test_exception_cannot_leak_hidden_expected(self, runner):
        """
        Learner code that raises an exception containing the expected output
        must NOT have that exception message surfaced for hidden tests.
        """
        code = """
def solution(x):
    raise ValueError(f"Expected output is probably {x * 3}")
"""
        test_cases = [_tc("h3", [7], 21, hidden=True)]
        result = runner.run(code, "solution", test_cases)
        tc = result.test_results[0]

        assert tc.error_message is None, (
            "Exception message must be None for hidden tests"
        )

    def test_hidden_pass_reveals_nothing_extra(self, runner):
        """Even a passing hidden test should not reveal inputs/outputs."""
        code = """
def solution(x):
    return x * 2
"""
        test_cases = [_tc("h4", [21], 42, hidden=True)]
        result = runner.run(code, "solution", test_cases)
        tc = result.test_results[0]

        assert tc.outcome == "passed"
        assert tc.actual_output is None
        assert tc.stdout is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Outcome labelling – correct canonical labels
# ─────────────────────────────────────────────────────────────────────────────

class TestOutcomeLabels:

    def test_correct_answer_is_passed(self, runner):
        code = "def solution(x): return x * 2"
        result = runner.run(code, "solution", [_tc("o1", [5], 10)])
        assert result.test_results[0].outcome == "passed"

    def test_wrong_answer_is_wrong_output(self, runner):
        code = "def solution(x): return x + 1"
        result = runner.run(code, "solution", [_tc("o2", [5], 10)])
        assert result.test_results[0].outcome == "wrong_output"

    def test_runtime_exception_is_runtime_error(self, runner):
        code = "def solution(x): return x / 0"
        result = runner.run(code, "solution", [_tc("o3", [5], 0)])
        assert result.test_results[0].outcome == "runtime_error"

    def test_timeout_label(self, runner):
        code = """
def solution(x):
    i = 0
    while True:
        i += 1
"""
        result = runner.run(code, "solution", [_tc("o4", [1], 1)])
        assert result.test_results[0].outcome == "timeout"

    def test_syntax_error_is_runtime_error(self, runner):
        code = "def solution(x) return x"  # missing colon
        result = runner.run(code, "solution", [_tc("o5", [1], 1)])
        assert result.test_results[0].outcome == "runtime_error"

    def test_all_outcomes_are_valid(self, runner):
        from app.services.test_runner import VALID_OUTCOMES
        code = "def solution(x): return x"
        result = runner.run(code, "solution", [_tc("o6", [1], 1)])
        for tc in result.test_results:
            assert tc.outcome in VALID_OUTCOMES, (
                f"Invalid outcome {tc.outcome!r} — must be one of {VALID_OUTCOMES}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Limit-hit attribution
# ─────────────────────────────────────────────────────────────────────────────

class TestLimitAttribution:

    def test_timeout_has_no_hidden_leakage(self, runner):
        """Even a timeout on a hidden test must not leak anything."""
        code = """
def solution(x):
    while True:
        pass
"""
        test_cases = [_tc("lim1", [1], 999, hidden=True)]
        result = runner.run(code, "solution", test_cases)
        tc = result.test_results[0]
        assert tc.outcome == "timeout"
        assert tc.error_message is None
        assert tc.actual_output is None
