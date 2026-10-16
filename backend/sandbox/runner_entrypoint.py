#!/usr/bin/env python3
"""
runner_entrypoint.py
====================
Debug Dojo – Sandbox execution entrypoint
------------------------------------------
THIS SCRIPT RUNS INSIDE THE DOCKER CONTAINER.

It receives a single JSON payload from stdin:
    {
        "code":       "<learner's Python source>",
        "fn_name":    "last_k_total",
        "test_cases": [
            {"test_id": "tc_01", "input_args": [[10,20,30], 2], "expected_output": 50},
            ...
        ],
        "per_test_timeout": 5.0   # seconds
    }

It writes a single JSON array to stdout (one object per test case).
STDERR is reserved for internal sandbox errors only.

Security rules enforced here:
  • No imports of os, subprocess, socket, sys.exit are allowed in user code
    (enforced by the RestrictedImporter).
  • Stdout is captured per-test and truncated to MAX_STDOUT_BYTES.
  • Wall-clock time is enforced with signal.SIGALRM per test.
  • The user code namespace is a shallow dict — no access to globals().
  • Any exception from user code is caught and serialised; its message is
    truncated to MAX_ERROR_BYTES before being returned to the caller.
"""

from __future__ import annotations

import gc
import io
import json
import math
import resource
import signal
import sys
import time
import traceback
import types
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_STDOUT_BYTES: int = 8 * 1024        # 8 KiB per test
MAX_ERROR_BYTES:  int = 2 * 1024        # 2 KiB for error messages
MAX_OUTPUT_REPR:  int = 512             # repr() length of actual output
DEFAULT_TIMEOUT:  float = 5.0          # seconds per test case

# Modules the learner code must NOT be able to import.
_BLOCKED_MODULES: frozenset[str] = frozenset({
    "os", "os.path", "subprocess", "socket", "ssl",
    "http", "urllib", "urllib.request", "urllib.parse",
    "ftplib", "smtplib", "telnetlib", "imaplib", "poplib",
    "socketserver", "xmlrpc", "asyncio", "multiprocessing",
    "threading",         # avoid hidden thread-based timeouts escapes
    "ctypes", "cffi",
    "importlib", "importlib.util", "importlib.machinery",
    "builtins",          # prevent __builtins__ hijacking
    "gc",                # prevent GC manipulation
    "sys",               # prevent sys.exit, sys.modules manipulation
    "signal",            # prevent alarm cancellation
    "resource",          # prevent rlimit manipulation
    "pty", "tty", "termios", "fcntl", "grp", "pwd",
    "mmap",
    "zipimport", "zipfile",
    "code", "codeop", "compileall",
    "dis", "inspect", "ast",          # prevent AST manipulation / introspection
    "tokenize", "token",
    "pickle", "shelve", "marshal",
    "struct",
    "tempfile",
    "shutil",
    "glob",
    "pathlib",
})


# ─────────────────────────────────────────────────────────────────────────────
# Restricted import hook
# ─────────────────────────────────────────────────────────────────────────────

class _RestrictedImporter:
    """
    A meta-path finder that raises ImportError for every module in
    _BLOCKED_MODULES (and their sub-modules) before the real finder runs.
    """

    def find_module(self, fullname: str, path: Any = None):  # Python 2 compat hook
        return self._check(fullname)

    def find_spec(self, fullname: str, path: Any, target: Any = None):
        return self._check(fullname)

    @staticmethod
    def _check(fullname: str):
        root = fullname.split(".")[0]
        if fullname in _BLOCKED_MODULES or root in _BLOCKED_MODULES:
            raise ImportError(
                f"[Sandbox] Import of '{fullname}' is not permitted."
            )
        return None  # let the real finders handle it


# ─────────────────────────────────────────────────────────────────────────────
# Safe built-ins whitelist
# ─────────────────────────────────────────────────────────────────────────────

def _make_safe_builtins() -> dict:
    """
    Return a tight whitelist of built-in names that learner code may use.
    Everything not listed here is stripped.
    """
    import builtins as _builtins

    _ALLOWED_BUILTINS = {
        # I/O (print only — capture redirects it)
        "print",
        # Type construction
        "int", "float", "str", "bool", "bytes", "bytearray",
        "list", "tuple", "dict", "set", "frozenset",
        "complex",
        # Iteration helpers
        "range", "enumerate", "zip", "map", "filter", "reversed", "sorted",
        "iter", "next",
        # Functional
        "len", "min", "max", "sum", "abs", "round", "divmod", "pow",
        "any", "all",
        # Conversion / inspection
        "repr", "str", "chr", "ord", "hex", "oct", "bin",
        "isinstance", "issubclass", "type", "id",
        "callable",
        # Object creation
        "object", "super",
        "property", "staticmethod", "classmethod",
        # Error types
        "Exception", "ValueError", "TypeError", "IndexError",
        "KeyError", "AttributeError", "StopIteration",
        "ArithmeticError", "ZeroDivisionError", "OverflowError",
        "RuntimeError", "NotImplementedError", "RecursionError",
        "MemoryError",
        # Misc
        "hash", "vars", "dir",
        "True", "False", "None",
        "NotImplemented", "Ellipsis",
    }

    safe: dict = {"__builtins__": {}}
    for name in _ALLOWED_BUILTINS:
        obj = getattr(_builtins, name, None)
        if obj is not None:
            safe["__builtins__"][name] = obj  # type: ignore[index]

    return safe


# ─────────────────────────────────────────────────────────────────────────────
# Timeout handler (SIGALRM – Linux only)
# ─────────────────────────────────────────────────────────────────────────────

class _TimeoutError(Exception):
    pass


def _alarm_handler(signum: int, frame: Any) -> None:
    raise _TimeoutError("Execution timed out.")


# ─────────────────────────────────────────────────────────────────────────────
# Core executor
# ─────────────────────────────────────────────────────────────────────────────

class _SandboxedExecutor:
    """
    Compiles the learner code once; executes it per test case in a
    restricted namespace.
    """

    def __init__(self, code: str, fn_name: str):
        self._fn_name = fn_name
        self._code = code
        self._compiled: types.CodeType | None = None
        self._compile_error: str | None = None

        try:
            self._compiled = compile(code, "<learner_submission>", "exec")
        except SyntaxError as exc:
            self._compile_error = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        except Exception as exc:
            self._compile_error = f"CompileError: {exc!r}"

    def run_test(
        self,
        test_id: str,
        input_args: list,
        expected_output: Any,
        timeout: float,
    ) -> dict:
        """
        Execute one test case.  Returns a raw result dict (not sanitized).
        The host-side test_runner.py performs sanitization for hidden tests.
        """
        if self._compile_error:
            return {
                "test_id": test_id,
                "outcome": "runtime_error",
                "error_message": self._compile_error,
                "actual_output": None,
                "stdout": "",
                "elapsed_ms": 0.0,
                "limit_hit": None,
            }

        # ── Per-test isolated namespace ───────────────────────────────────────
        namespace = _make_safe_builtins()
        namespace.update({
            "__name__": "__sandbox__",
            "__file__": "<learner_submission>",
        })

        # ── Capture stdout ────────────────────────────────────────────────────
        captured_stdout = io.StringIO()
        real_stdout = sys.stdout
        sys.stdout = captured_stdout

        actual_output: Any = None
        error_message: str | None = None
        limit_hit: str | None = None
        elapsed_ms: float = 0.0
        outcome: str = "wrong_output"

        # ── Set SIGALRM wall-clock timeout ────────────────────────────────────
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)

        t_start = time.perf_counter()
        try:
            # Execute the learner's code (defines functions, classes, etc.)
            exec(self._compiled, namespace)  # noqa: S102

            # Retrieve the target function
            fn = namespace.get(self._fn_name)
            if fn is None or not callable(fn):
                raise RuntimeError(
                    f"Function '{self._fn_name}' was not defined in the submission."
                )

            # Call the function — deep-copy args so mutations don't bleed
            import copy
            safe_args = copy.deepcopy(input_args)
            actual_output = fn(*safe_args)

        except _TimeoutError:
            outcome = "timeout"
            error_message = "Time limit exceeded."

        except MemoryError:
            outcome = "runtime_error"
            error_message = "runtime_error: memory limit exceeded"
            limit_hit = "memory"
            gc.collect()

        except RecursionError:
            outcome = "runtime_error"
            error_message = "runtime_error: recursion depth exceeded (stack overflow)"
            limit_hit = "recursion"

        except OverflowError as exc:
            outcome = "runtime_error"
            error_message = f"runtime_error: numeric overflow — {_truncate(str(exc), MAX_ERROR_BYTES)}"

        except Exception as exc:
            outcome = "runtime_error"
            tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            raw = "".join(tb_lines)
            # Strip internal frames that reveal sandbox internals
            safe_tb = _strip_internal_frames(raw)
            error_message = _truncate(safe_tb, MAX_ERROR_BYTES)

        else:
            # No exception → compare output
            if _outputs_equal(actual_output, expected_output):
                outcome = "passed"
            else:
                outcome = "wrong_output"

        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)   # cancel alarm
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            sys.stdout = real_stdout

        stdout_content = _truncate(captured_stdout.getvalue(), MAX_STDOUT_BYTES)

        return {
            "test_id": test_id,
            "outcome": outcome,
            "actual_output": _safe_repr(actual_output),
            "stdout": stdout_content,
            "elapsed_ms": round(elapsed_ms, 3),
            "error_message": error_message,
            "limit_hit": limit_hit,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Comparison helper
# ─────────────────────────────────────────────────────────────────────────────

def _outputs_equal(actual: Any, expected: Any) -> bool:
    """
    Flexible equality that handles float precision and JSON null → None.
    """
    if expected is None:
        # Seed uses null for "check manually" cases; treat as passed.
        return True
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9)
    return actual == expected


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _truncate(s: str, max_bytes: int) -> str:
    encoded = s.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return s
    return encoded[:max_bytes].decode("utf-8", errors="replace") + "…[truncated]"


def _safe_repr(obj: Any) -> str | None:
    if obj is None:
        return None
    try:
        r = repr(obj)
        return _truncate(r, MAX_OUTPUT_REPR)
    except Exception:
        return "<unprintable>"


def _strip_internal_frames(tb: str) -> str:
    """
    Remove lines that reference the sandbox runner itself so learners
    don't see internal implementation details.
    """
    lines = tb.splitlines(keepends=True)
    filtered = [
        ln for ln in lines
        if "runner_entrypoint.py" not in ln
        and "<learner_submission>" in ln or "Error" in ln or ln.strip().startswith("^")
        or not ln.strip().startswith('File "')
    ]
    return "".join(filtered)


# ─────────────────────────────────────────────────────────────────────────────
# Resource limits (belt-and-suspenders, enforced inside the container too)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_rlimits() -> None:
    """
    Apply conservative rlimits from within the process.
    Docker --memory already enforces the cgroup memory limit;
    these act as an additional inner fence.
    """
    MB = 1024 * 1024

    limits = [
        # (resource constant, soft, hard)
        (resource.RLIMIT_AS,       256 * MB,  256 * MB),   # virtual address space
        (resource.RLIMIT_DATA,     128 * MB,  128 * MB),   # heap
        (resource.RLIMIT_STACK,     8  * MB,    8 * MB),   # stack
        (resource.RLIMIT_FSIZE,    16  * MB,   16 * MB),   # max file write
        (resource.RLIMIT_NOFILE,   64,          64),        # open file descriptors
        (resource.RLIMIT_NPROC,     1,            1),       # no new processes
        (resource.RLIMIT_CPU,      10,           10),       # CPU seconds (hard cap)
    ]

    for res, soft, hard in limits:
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, resource.error):
            pass  # some limits may already be tighter from cgroup


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Apply resource limits before doing anything ───────────────────────────
    _apply_rlimits()

    # ── Install restricted importer ───────────────────────────────────────────
    sys.meta_path.insert(0, _RestrictedImporter())

    # ── Read payload ──────────────────────────────────────────────────────────
    try:
        raw = sys.stdin.buffer.read()
        payload: dict = json.loads(raw)
    except Exception as exc:
        json.dump(
            {"error": f"Failed to parse payload: {exc!r}"},
            sys.stdout,
        )
        sys.exit(1)

    code: str = payload.get("code", "")
    fn_name: str = payload.get("fn_name", "solution")
    test_cases: list = payload.get("test_cases", [])
    per_test_timeout: float = float(payload.get("per_test_timeout", DEFAULT_TIMEOUT))

    # Clamp timeout to safe bounds
    per_test_timeout = max(0.5, min(per_test_timeout, 10.0))

    executor = _SandboxedExecutor(code, fn_name)
    results: list[dict] = []

    for tc in test_cases:
        result = executor.run_test(
            test_id=tc.get("test_id", "unknown"),
            input_args=tc.get("input_args", []),
            expected_output=tc.get("expected_output"),
            timeout=per_test_timeout,
        )
        results.append(result)

    # Write results to stdout as a single JSON line
    sys.stdout.write(json.dumps(results, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
