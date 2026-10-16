"""
test_runner.py
==============
Debug Dojo – Secure Test Runner Service
-----------------------------------------
This module is the HOST-SIDE orchestrator.  It:

  1. Serialises the learner's code + test cases into a JSON payload.
  2. Spawns a hardened Docker container with strict resource constraints.
  3. Sends the payload via stdin; reads JSON results from stdout.
  4. Maps raw container results to exactly one of the four canonical outcomes:
         passed | wrong_output | runtime_error | timeout
  5. Sanitises the payload before returning:
       • Hidden tests NEVER expose input_args, expected_output, actual_output,
         stdout, or error_message — only test_id + outcome.

Security constraints enforced at the Docker layer
--------------------------------------------------
  --network none          → zero network access
  --read-only             → root filesystem read-only
  --tmpfs /tmp:…          → size-limited writable scratch (noexec, nosuid)
  --memory / --memory-swap→ RAM cap (default 128 MiB)
  --cpus                  → CPU fraction cap (default 0.5 vCPU)
  --pids-limit            → prevents fork bombs (default 64)
  --cap-drop ALL          → no Linux capabilities
  --no-new-privileges     → no privilege escalation via setuid
  --security-opt seccomp  → custom syscall whitelist
  --user 65534:65534      → runs as nobody:nobody

Usage
-----
    from app.services.test_runner import TestRunner, RunnerConfig

    runner = TestRunner()
    result = runner.run(
        code="def last_k_total(marks, k): return sum(marks[-k:] if k else [])",
        fn_name="last_k_total",
        test_cases=[
            {"test_id": "tc1", "input_args": [[10,20,30], 2], "expected_output": 50, "is_hidden": False},
            ...
        ],
    )
    print(result.to_dict())
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_SANDBOX_DIR = Path(__file__).parent.parent.parent / "sandbox"
_SECCOMP_PROFILE = _SANDBOX_DIR / "seccomp_profile.json"
_DOCKER_IMAGE = os.environ.get("SANDBOX_IMAGE", "debug-dojo-sandbox:latest")


@dataclass(frozen=True)
class RunnerConfig:
    """Tunable resource limits for a sandbox run."""

    memory_mb: int = 128          # MiB of RAM (cgroup hard limit)
    cpu_fraction: float = 0.5     # fraction of one vCPU
    pids_limit: int = 64          # max OS PIDs (blocks fork bombs)
    per_test_timeout_s: float = 5.0  # wall-clock seconds per test case
    container_timeout_s: float = 60.0  # overall docker run wall-clock timeout
    tmpfs_size_mb: int = 16       # writable scratch space in /tmp


# ─────────────────────────────────────────────────────────────────────────────
# Result data-classes
# ─────────────────────────────────────────────────────────────────────────────

# The four canonical outcome labels — nothing else is ever returned to callers.
VALID_OUTCOMES = frozenset({"passed", "wrong_output", "runtime_error", "timeout"})


@dataclass
class TestCaseResult:
    """Result for a single test case (after sanitisation)."""

    test_id: str
    outcome: str                   # one of VALID_OUTCOMES
    is_hidden: bool = False

    # Fields below are ONLY populated for visible tests.
    actual_output: str | None = None  # repr() of the return value
    stdout: str | None = None
    elapsed_ms: float | None = None
    error_message: str | None = None  # set for runtime_error/timeout
    limit_hit: str | None = None      # "memory" | "disk" | "cpu" | "recursion" | None

    def to_dict(self) -> dict:
        base = {
            "test_id": self.test_id,
            "outcome": self.outcome,
            "is_hidden": self.is_hidden,
        }
        if not self.is_hidden:
            base.update({
                "actual_output": self.actual_output,
                "stdout": self.stdout,
                "elapsed_ms": self.elapsed_ms,
                "error_message": self.error_message,
                "limit_hit": self.limit_hit,
            })
        return base


@dataclass
class RunResult:
    """Aggregated result for a full submission run."""

    submission_id: str
    fn_name: str
    overall_outcome: str           # "passed" | "failed" | "error" | "timeout"
    total_tests: int = 0
    passed_tests: int = 0
    test_results: list[TestCaseResult] = field(default_factory=list)
    sandbox_error: str | None = None   # set if the container itself crashed

    def to_dict(self) -> dict:
        return {
            "submission_id": self.submission_id,
            "fn_name": self.fn_name,
            "overall_outcome": self.overall_outcome,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "test_results": [r.to_dict() for r in self.test_results],
            "sandbox_error": self.sandbox_error,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Outcome mapping
# ─────────────────────────────────────────────────────────────────────────────

def _map_outcome(raw: dict) -> tuple[str, str | None, str | None]:
    """
    Map raw container output to (canonical_outcome, error_message, limit_hit).

    The container may report special limit messages; we surface them explicitly
    so the caller knows *which* limit was hit.
    """
    outcome: str = raw.get("outcome", "runtime_error")

    if outcome not in VALID_OUTCOMES:
        outcome = "runtime_error"

    error_msg: str | None = raw.get("error_message")
    limit_hit: str | None = raw.get("limit_hit")

    # Normalise container-emitted limit phrases into canonical labels.
    if error_msg:
        lower = error_msg.lower()
        if "memory limit" in lower:
            outcome = "runtime_error"
            limit_hit = "memory"
            error_msg = "runtime_error: memory limit exceeded"
        elif "disk" in lower or "file size" in lower or "fsize" in lower:
            outcome = "runtime_error"
            limit_hit = "disk"
            error_msg = "runtime_error: disk write limit exceeded"
        elif "cpu" in lower or "cpu time" in lower:
            outcome = "runtime_error"
            limit_hit = "cpu"
            error_msg = "runtime_error: CPU time limit exceeded"
        elif "time limit" in lower or "timed out" in lower:
            outcome = "timeout"

    return outcome, error_msg, limit_hit


# ─────────────────────────────────────────────────────────────────────────────
# Sanitisation
# ─────────────────────────────────────────────────────────────────────────────

def _sanitise(
    raw_result: dict,
    is_hidden: bool,
) -> TestCaseResult:
    """
    Build a :class:`TestCaseResult` from the raw container dict.

    For hidden tests, ONLY test_id + outcome are retained.
    ALL other fields — including actual_output, stdout, error_message —
    are dropped unconditionally.  This prevents data leakage even if the
    learner's code explicitly prints() the test inputs or raises them in
    an exception message.
    """
    outcome, error_msg, limit_hit = _map_outcome(raw_result)

    if is_hidden:
        # ── Hidden test: zero information leakage ────────────────────────────
        return TestCaseResult(
            test_id=raw_result.get("test_id", "unknown"),
            outcome=outcome,
            is_hidden=True,
            # All sensitive fields explicitly set to None — not just absent.
            actual_output=None,
            stdout=None,
            elapsed_ms=None,
            error_message=None,
            limit_hit=None,
        )

    # ── Visible test: full detail ─────────────────────────────────────────────
    return TestCaseResult(
        test_id=raw_result.get("test_id", "unknown"),
        outcome=outcome,
        is_hidden=False,
        actual_output=raw_result.get("actual_output"),
        stdout=raw_result.get("stdout"),
        elapsed_ms=raw_result.get("elapsed_ms"),
        error_message=error_msg,
        limit_hit=limit_hit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Docker runner
# ─────────────────────────────────────────────────────────────────────────────

class TestRunner:
    """
    Host-side orchestrator that launches the sandbox container, passes the
    learner payload, and returns a sanitised :class:`RunResult`.
    """

    def __init__(self, config: RunnerConfig | None = None) -> None:
        self.config = config or RunnerConfig()
        self._seccomp_path = str(_SECCOMP_PROFILE.resolve())

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        code: str,
        fn_name: str,
        test_cases: list[dict],
        *,
        submission_id: str | None = None,
    ) -> RunResult:
        """
        Execute *code* against every test case in *test_cases* inside the
        sandbox and return a sanitised :class:`RunResult`.

        Parameters
        ----------
        code:
            Raw Python source submitted by the learner.
        fn_name:
            Name of the function to call, e.g. ``"last_k_total"``.
        test_cases:
            List of dicts; each must have:
              test_id, input_args, expected_output, is_hidden
        submission_id:
            Optional UUID string for correlation; generated if omitted.
        """
        sub_id = submission_id or str(uuid.uuid4())

        # Build the payload for the container
        payload = self._build_payload(code, fn_name, test_cases)

        # Execute inside Docker
        raw_results, sandbox_error = self._docker_run(payload)

        # Build the RunResult
        return self._build_run_result(
            sub_id, fn_name, test_cases, raw_results, sandbox_error
        )

    # ── Internal: payload construction ───────────────────────────────────────

    def _build_payload(
        self,
        code: str,
        fn_name: str,
        test_cases: list[dict],
    ) -> bytes:
        """
        Serialise the payload that will be piped to the container's stdin.
        Note: is_hidden is NOT included — the container never knows which
        tests are hidden.  That information stays on the host side only.
        """
        container_tests = [
            {
                "test_id": tc["test_id"],
                "input_args": tc["input_args"],
                "expected_output": tc["expected_output"],
                # is_hidden intentionally omitted from container payload
            }
            for tc in test_cases
        ]

        return json.dumps(
            {
                "code": code,
                "fn_name": fn_name,
                "test_cases": container_tests,
                "per_test_timeout": self.config.per_test_timeout_s,
            },
            ensure_ascii=False,
        ).encode("utf-8")

    # ── Internal: Docker execution ────────────────────────────────────────────

    def _build_docker_cmd(self) -> list[str]:
        """
        Construct the docker run command with all security flags.
        Every flag is explicit and intentional.
        """
        cfg = self.config
        mem = f"{cfg.memory_mb}m"

        cmd = [
            "docker", "run",
            "--rm",                                      # auto-remove on exit
            "--interactive",                             # accept stdin

            # ── Identity ─────────────────────────────────────────────────────
            "--user", "65534:65534",                     # nobody:nobody

            # ── Network isolation ─────────────────────────────────────────────
            "--network", "none",                         # NO network

            # ── Filesystem isolation ──────────────────────────────────────────
            "--read-only",                               # root fs read-only
            "--tmpfs", f"/tmp:size={cfg.tmpfs_size_mb}m,noexec,nosuid,nodev",

            # ── Compute limits ────────────────────────────────────────────────
            "--memory", mem,                             # RAM hard cap
            "--memory-swap", mem,                        # disable swap
            "--cpus", str(cfg.cpu_fraction),             # CPU fraction
            "--pids-limit", str(cfg.pids_limit),         # PID cap (fork bomb guard)

            # ── Privilege reduction ───────────────────────────────────────────
            "--cap-drop", "ALL",                         # drop all capabilities
            "--no-new-privileges",                       # no setuid escalation

            # ── Syscall filtering ─────────────────────────────────────────────
            "--security-opt", f"seccomp={self._seccomp_path}",

            # ── Misc hardening ────────────────────────────────────────────────
            "--security-opt", "no-new-privileges",
            "--ulimit", "nofile=64:64",                  # file descriptor cap
            "--ulimit", f"fsize={cfg.tmpfs_size_mb * 1024 * 1024}",  # write cap

            # ── Image ─────────────────────────────────────────────────────────
            _DOCKER_IMAGE,
        ]
        return cmd

    def _docker_run(
        self, payload: bytes
    ) -> tuple[list[dict], str | None]:
        """
        Spin up the container, pipe *payload* to stdin, collect stdout.

        Returns
        -------
        (raw_results, sandbox_error)
            raw_results  – list of raw result dicts (may be empty on failure)
            sandbox_error – human-readable error string if the container failed
        """
        cmd = self._build_docker_cmd()
        sandbox_error: str | None = None
        raw_results: list[dict] = []

        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                timeout=self.config.container_timeout_s,
            )
        except subprocess.TimeoutExpired:
            logger.error("Container wall-clock timeout exceeded.")
            return [], "Container timed out."
        except FileNotFoundError:
            return [], "Docker is not installed or not in PATH."
        except Exception as exc:
            return [], f"Unexpected runner error: {exc!r}"

        stdout = proc.stdout.decode("utf-8", errors="replace").strip()
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0 and not stdout:
            # Container exited with error before producing any output.
            detail = stderr[:500] if stderr else f"exit code {proc.returncode}"
            sandbox_error = f"Sandbox container error: {detail}"
            logger.warning("Sandbox error: %s", sandbox_error)
            return [], sandbox_error

        if not stdout:
            return [], "Sandbox produced no output."

        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, list):
                raw_results = parsed
            elif isinstance(parsed, dict) and "error" in parsed:
                sandbox_error = parsed["error"]
            else:
                sandbox_error = "Malformed sandbox output."
        except json.JSONDecodeError as exc:
            sandbox_error = f"Could not parse sandbox output: {exc}"
            logger.error("JSON parse error: %s\nRaw: %r", exc, stdout[:500])

        return raw_results, sandbox_error

    # ── Internal: result assembly ─────────────────────────────────────────────

    def _build_run_result(
        self,
        submission_id: str,
        fn_name: str,
        test_cases: list[dict],
        raw_results: list[dict],
        sandbox_error: str | None,
    ) -> RunResult:
        """
        Map raw container results → sanitised TestCaseResult objects.
        The is_hidden metadata is re-joined from the original test_cases list
        (never from the container output).
        """
        # Build a map of test_id → is_hidden from the host-side data.
        hidden_map: dict[str, bool] = {
            tc["test_id"]: tc.get("is_hidden", False)
            for tc in test_cases
        }

        tc_results: list[TestCaseResult] = []

        if sandbox_error and not raw_results:
            # Container-level failure: mark every test as runtime_error.
            for tc in test_cases:
                is_hidden = hidden_map.get(tc["test_id"], False)
                tc_results.append(
                    TestCaseResult(
                        test_id=tc["test_id"],
                        outcome="runtime_error",
                        is_hidden=is_hidden,
                        error_message=None if is_hidden else "Sandbox error: container failed to start.",
                    )
                )
        else:
            # Build index for O(1) lookup
            raw_by_id: dict[str, dict] = {r["test_id"]: r for r in raw_results}

            for tc in test_cases:
                tid = tc["test_id"]
                is_hidden = hidden_map.get(tid, False)
                raw = raw_by_id.get(tid)

                if raw is None:
                    # Test was never executed (container bailed early).
                    tc_results.append(
                        TestCaseResult(
                            test_id=tid,
                            outcome="runtime_error",
                            is_hidden=is_hidden,
                            error_message=None if is_hidden else "Test not executed (sandbox bailed).",
                        )
                    )
                else:
                    tc_results.append(_sanitise(raw, is_hidden))

        passed = sum(1 for r in tc_results if r.outcome == "passed")
        total = len(tc_results)

        # Derive overall outcome
        if sandbox_error and not raw_results:
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
            submission_id=submission_id,
            fn_name=fn_name,
            overall_outcome=overall,
            total_tests=total,
            passed_tests=passed,
            test_results=tc_results,
            sandbox_error=sandbox_error,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience factory — cached shared runner instance
# ─────────────────────────────────────────────────────────────────────────────

_default_runner: TestRunner | None = None


def get_runner(config: RunnerConfig | None = None) -> TestRunner:
    """Return a module-level singleton TestRunner (lazily initialised)."""
    global _default_runner
    if _default_runner is None:
        _default_runner = TestRunner(config)
    return _default_runner
