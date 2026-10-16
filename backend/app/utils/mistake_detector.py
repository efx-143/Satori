"""
mistake_detector.py
====================
Debug Dojo – Mistake Taxonomy Utility
--------------------------------------
Analyses a learner's raw Python code string using the ``ast`` module and
targeted regex patterns to detect five structural mistake categories:

    1. off_by_one           – loop-range or slice boundary errors
    2. unhandled_short_input – missing guards for empty / short inputs
    3. print_not_return     – using print() instead of return
    4. boundary_comparison  – strict inequality where ≤/≥ is needed
    5. mutates_input        – in-place modification of argument variables

Usage
-----
    from app.utils.mistake_detector import detect_mistakes

    result = detect_mistakes(code_string)
    # → MistakeReport(tags=[...], details={...})

Each detector is an independent function so it can be unit-tested or
swapped out individually.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MistakeReport:
    """Container returned by :func:`detect_mistakes`."""

    tags: List[str] = field(default_factory=list)
    """Active mistake category slugs, e.g. ``["off_by_one", "print_not_return"]``."""

    details: Dict[str, Any] = field(default_factory=dict)
    """Per-tag detail dict: ``{tag: [{"line": int, "reason": str}, ...]}``."""

    parse_error: str | None = None
    """Set if the code could not be parsed; individual detectors are skipped."""

    def to_dict(self) -> dict:
        return {
            "tags": self.tags,
            "details": self.details,
            "parse_error": self.parse_error,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_parse(code: str) -> ast.Module | None:
    """Return the AST root or None on syntax error."""
    try:
        return ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return None


def _func_param_names(tree: ast.Module) -> set[str]:
    """
    Collect every top-level and nested function parameter name.
    Used by the mutates-input detector.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                names.add(arg.arg)
            if node.args.vararg:
                names.add(node.args.vararg.arg)
            if node.args.kwarg:
                names.add(node.args.kwarg.arg)
    return names


def _lineno(node: ast.AST) -> int:
    return getattr(node, "lineno", -1)


# ─────────────────────────────────────────────────────────────────────────────
# Detector 1 – off_by_one
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that strongly suggest an off-by-one mistake:
#   • range(1, n) or range(0, n-1) – likely skips first/last element
#   • slice ending at len(x)-1     – should use len(x)
_OBO_RANGE_PATTERNS = [
    # range(1, ...)  – probably should start at 0
    re.compile(r'\brange\s*\(\s*1\s*,'),
    # range(..., len(x) - 1) or range(..., n - 1)  – typically off-by-one
    re.compile(r'\brange\s*\([^)]*(?:len\s*\([^)]*\)|\bn\b)\s*-\s*1\s*\)'),
]

_OBO_SLICE_PATTERN = re.compile(
    r'\[.*?:.*?(?:len\s*\([^)]*\)|[a-zA-Z_]\w*)\s*-\s*1\s*\]'
)


def detect_off_by_one(tree: ast.Module, source_lines: list[str]) -> list[dict]:
    """
    Detect potential off-by-one errors in loop ranges and slice boundaries.

    Strategy
    --------
    * Walk the AST for ``ast.Call`` nodes whose function is ``range``; inspect
      the ``start`` and ``stop`` arguments for literal 1-starts or ``n-1``
      stop values.
    * Walk for ``ast.Subscript`` nodes whose slice is a ``BinOp`` of the form
      ``x - 1`` which almost always signals a forgotten boundary.
    * Supplement with a line-level regex sweep for patterns the AST might miss
      (e.g. inside comprehensions).
    """
    findings: list[dict] = []

    for node in ast.walk(tree):
        # ── range() calls ────────────────────────────────────────────────────
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "range" and node.args:
                # range(1, ...) — start offset at 1 is suspicious
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and first_arg.value == 1:
                    if len(node.args) >= 2:
                        findings.append({
                            "line": _lineno(node),
                            "reason": (
                                "range() starts at 1 — this skips index 0; "
                                "should it start at 0?"
                            ),
                        })

                # range(..., x - 1) — stop is n-1 instead of n
                if len(node.args) >= 2:
                    stop_arg = node.args[1]
                    if (
                        isinstance(stop_arg, ast.BinOp)
                        and isinstance(stop_arg.op, ast.Sub)
                        and isinstance(stop_arg.right, ast.Constant)
                        and stop_arg.right.value == 1
                    ):
                        findings.append({
                            "line": _lineno(node),
                            "reason": (
                                "range() stop is 'x - 1' — may miss the last "
                                "element; consider using 'x' directly."
                            ),
                        })

        # ── Slice with x - 1 upper bound ─────────────────────────────────────
        if isinstance(node, ast.Subscript):
            slc = node.slice
            # Python 3.9+: slice is directly an ast.Slice; earlier wraps in Index
            if isinstance(slc, ast.Slice) and slc.upper is not None:
                upper = slc.upper
                if (
                    isinstance(upper, ast.BinOp)
                    and isinstance(upper.op, ast.Sub)
                    and isinstance(upper.right, ast.Constant)
                    and upper.right.value == 1
                ):
                    findings.append({
                        "line": _lineno(node),
                        "reason": (
                            "Slice upper bound is 'x - 1' — Python slices are "
                            "exclusive, so this likely drops the last element."
                        ),
                    })

    # ── Regex sweep (catches remaining patterns) ──────────────────────────────
    for i, line in enumerate(source_lines, start=1):
        for pattern in _OBO_RANGE_PATTERNS:
            if pattern.search(line):
                # Avoid double-reporting lines already captured by the AST walk
                already = any(f["line"] == i for f in findings)
                if not already:
                    findings.append({
                        "line": i,
                        "reason": f"Potential off-by-one in: {line.strip()!r}",
                    })
        if _OBO_SLICE_PATTERN.search(line):
            already = any(f["line"] == i for f in findings)
            if not already:
                findings.append({
                    "line": i,
                    "reason": (
                        f"Slice ending at 'len(x)-1' on line {i}: "
                        f"{line.strip()!r}"
                    ),
                })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Detector 2 – unhandled_short_input
# ─────────────────────────────────────────────────────────────────────────────

def detect_unhandled_short_input(tree: ast.Module) -> list[dict]:
    """
    Detect missing guards for empty or short input lists/strings.

    Strategy
    --------
    * Check whether any top-level function that has a list/sequence parameter
      (heuristic: name contains 'list', 'items', 'marks', 'nums', 'arr', or
      the function accesses an index) contains *any* ``if len(...)`` or
      ``if not ...`` guard before performing indexing or slicing.
    * Flag functions that index (``node[0]``, ``node[-1]``) or slice
      (``node[a:b]``) a parameter without a preceding length/empty check.
    """
    findings: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        param_names = {a.arg for a in node.args.args}
        if not param_names:
            continue

        # Collect all subscript operations on known parameters
        has_index_or_slice = False
        has_guard = False

        for child in ast.walk(node):
            # Guard patterns: `if not x`, `if len(x) ...`, `if x is None`
            if isinstance(child, ast.If):
                test = child.test
                # `if not param`
                if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                    if isinstance(test.operand, ast.Name) and test.operand.id in param_names:
                        has_guard = True
                # `if len(param) ...`
                if isinstance(test, ast.Call):
                    if (
                        isinstance(test.func, ast.Name)
                        and test.func.id == "len"
                        and test.args
                        and isinstance(test.args[0], ast.Name)
                        and test.args[0].id in param_names
                    ):
                        has_guard = True
                # `if len(param) < n`, `if len(param) == 0` etc. (Compare)
                if isinstance(test, ast.Compare):
                    left = test.left
                    if (
                        isinstance(left, ast.Call)
                        and isinstance(left.func, ast.Name)
                        and left.func.id == "len"
                        and left.args
                        and isinstance(left.args[0], ast.Name)
                        and left.args[0].id in param_names
                    ):
                        has_guard = True

            # Direct indexing: param[0], param[-1], param[i]
            if isinstance(child, ast.Subscript):
                value = child.value
                if isinstance(value, ast.Name) and value.id in param_names:
                    slc = child.slice
                    # Exclude pure slice (handled differently); flag constant index
                    if not isinstance(slc, ast.Slice):
                        has_index_or_slice = True

        if has_index_or_slice and not has_guard:
            findings.append({
                "line": _lineno(node),
                "reason": (
                    f"Function '{node.name}' indexes a parameter directly "
                    "without first checking if the input is empty or long enough."
                ),
            })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Detector 3 – print_not_return
# ─────────────────────────────────────────────────────────────────────────────

def detect_print_not_return(tree: ast.Module) -> list[dict]:
    """
    Detect functions that call ``print()`` but never ``return`` a value.

    Strategy
    --------
    For each function definition, collect all ``ast.Call`` nodes whose
    function is ``print``.  Separately, collect all ``ast.Return`` nodes
    that have a non-None value.  If the function prints but never returns a
    meaningful value, flag it.
    """
    findings: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        has_print = False
        has_return_value = False
        print_lines: list[int] = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if (
                    (isinstance(func, ast.Name) and func.id == "print")
                    or (isinstance(func, ast.Attribute) and func.attr == "print")
                ):
                    has_print = True
                    print_lines.append(_lineno(child))

            if isinstance(child, ast.Return) and child.value is not None:
                # A bare `return None` or `return` also counts as no value
                if not (
                    isinstance(child.value, ast.Constant)
                    and child.value.value is None
                ):
                    has_return_value = True

        if has_print and not has_return_value:
            for ln in print_lines:
                findings.append({
                    "line": ln,
                    "reason": (
                        f"Function '{node.name}' uses print() but has no "
                        "return statement — the caller will receive None."
                    ),
                })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Detector 4 – boundary_comparison
# ─────────────────────────────────────────────────────────────────────────────

# Common thresholds that suggest the boundary should be inclusive (≥/≤)
_INCLUSIVE_THRESHOLDS = {0, 1, -1}

# Challenge-specific known thresholds (pass mark)
_DOMAIN_THRESHOLDS: dict[str, str] = {
    # value → hint
    "40": "pass mark (should be >= 40, not > 40)",
    "39": "pass mark (should be < 40, not <= 39)",
}


def detect_boundary_comparison(tree: ast.Module) -> list[dict]:
    """
    Detect strict inequalities (``<`` / ``>``) where inclusive ones
    (``<=`` / ``>=``) are more likely correct.

    Strategy
    --------
    Walk all ``ast.Compare`` nodes.  For each comparator pair, flag:

    * Strict ``<`` or ``>`` comparisons against well-known inclusive thresholds
      (0, 1, -1, 40 for the pass-mark domain).
    * ``> 0`` where ``>= 1`` is more natural for lengths.
    * ``< len(x)`` without a ``-1`` adjustment (that's actually correct, but
      ``< len(x) - 1`` is suspicious).
    """
    findings: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue

        left = node.left
        for op, comparator in zip(node.ops, node.comparators):
            # Extract numeric literal on either side
            literal_val: int | float | None = None
            if isinstance(comparator, ast.Constant) and isinstance(
                comparator.value, (int, float)
            ):
                literal_val = comparator.value
            elif isinstance(left, ast.Constant) and isinstance(
                left.value, (int, float)
            ):
                literal_val = left.value

            if literal_val is None:
                continue

            is_strict_lt = isinstance(op, ast.Lt)
            is_strict_gt = isinstance(op, ast.Gt)

            # Pattern: x > 0  (should it be x >= 1 ?)
            if is_strict_gt and literal_val == 0:
                findings.append({
                    "line": _lineno(node),
                    "reason": (
                        "Strict '> 0' detected — for counting/length checks, "
                        "'>= 1' is often more explicit and correct."
                    ),
                })

            # Pattern: x < 1 (should it be x <= 0 ?)
            if is_strict_lt and literal_val == 1:
                findings.append({
                    "line": _lineno(node),
                    "reason": (
                        "Strict '< 1' — consider '<= 0' if testing for "
                        "empty / non-positive values."
                    ),
                })

            # Domain-specific: pass mark threshold
            str_val = str(int(literal_val)) if isinstance(literal_val, float) and literal_val.is_integer() else str(literal_val)
            if str_val in _DOMAIN_THRESHOLDS:
                if is_strict_lt or is_strict_gt:
                    hint = _DOMAIN_THRESHOLDS[str_val]
                    findings.append({
                        "line": _lineno(node),
                        "reason": (
                            f"Strict comparison against {literal_val} — {hint}."
                        ),
                    })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Detector 5 – mutates_input
# ─────────────────────────────────────────────────────────────────────────────

# Method calls that mutate a list in-place
_MUTATING_METHODS = frozenset({
    "append", "extend", "insert", "remove", "pop",
    "clear", "sort", "reverse", "update", "discard",
    "add",   # set mutation
    "__setitem__",
})

# Augmented assignment operators that mutate the left-hand side
_AUGMENTED_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)


def detect_mutates_input(tree: ast.Module) -> list[dict]:
    """
    Detect in-place mutation of function arguments.

    Strategy
    --------
    For each function, gather parameter names then walk its body for:

    * ``param.append(...)``, ``param.pop()``, ``param.sort()`` etc.
    * ``param[i] = value``  — direct index assignment.
    * ``param += [...]``    — augmented assignment on the parameter itself.
    * ``param[:] = [...]``  — slice assignment (full replacement in-place).
    """
    findings: list[dict] = []

    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        param_names = {a.arg for a in func_node.args.args}
        if not param_names:
            continue

        for child in ast.walk(func_node):
            # ── Method calls: param.method(...) ──────────────────────────────
            if isinstance(child, ast.Call):
                func = child.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr in _MUTATING_METHODS
                    and isinstance(func.value, ast.Name)
                    and func.value.id in param_names
                ):
                    findings.append({
                        "line": _lineno(child),
                        "reason": (
                            f"Calls '{func.value.id}.{func.attr}()' which "
                            "mutates the input argument in-place. "
                            "Return a new list instead."
                        ),
                    })

            # ── Index assignment: param[i] = value ───────────────────────────
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in param_names
                    ):
                        findings.append({
                            "line": _lineno(child),
                            "reason": (
                                f"Direct assignment to '{target.value.id}[...]' "
                                "mutates the input list. Work on a copy instead."
                            ),
                        })

            # ── Augmented assignment: param += [...] ──────────────────────────
            if isinstance(child, ast.AugAssign):
                if (
                    isinstance(child.target, ast.Name)
                    and child.target.id in param_names
                ):
                    findings.append({
                        "line": _lineno(child),
                        "reason": (
                            f"Augmented assignment '{'+'}{'}='} {child.target.id}' "
                            "may mutate the original input (for lists, '+=' calls "
                            "'extend' in-place). Use a local copy."
                        ),
                    })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def detect_mistakes(code: str) -> MistakeReport:
    """
    Run all five mistake detectors against *code* and return a
    :class:`MistakeReport`.

    Parameters
    ----------
    code:
        Raw Python source code string submitted by a learner.

    Returns
    -------
    MistakeReport
        Contains ``tags`` (list of active mistake slugs) and ``details``
        (per-tag list of ``{line, reason}`` dicts).  ``parse_error`` is
        set instead if the code cannot be parsed.
    """
    report = MistakeReport()

    tree = _safe_parse(code)
    if tree is None:
        report.parse_error = "Code could not be parsed – check for syntax errors."
        return report

    source_lines = code.splitlines()

    # ── Run detectors ─────────────────────────────────────────────────────────
    detectors: list[tuple[str, list[dict]]] = [
        ("off_by_one",            detect_off_by_one(tree, source_lines)),
        ("unhandled_short_input", detect_unhandled_short_input(tree)),
        ("print_not_return",      detect_print_not_return(tree)),
        ("boundary_comparison",   detect_boundary_comparison(tree)),
        ("mutates_input",         detect_mutates_input(tree)),
    ]

    for tag, findings in detectors:
        if findings:
            report.tags.append(tag)
            report.details[tag] = findings

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Quick smoke-test (run as __main__)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    _BAD_CODE = """
def count_passes(marks):
    count = 0
    for i in range(1, len(marks)):   # off-by-one: starts at 1
        if marks[i] > 40:            # boundary: should be >= 40
            count += 1
    print(count)                     # print-not-return
    marks.append(0)                  # mutates input
"""

    result = detect_mistakes(_BAD_CODE)
    print("=== Mistake Report ===")
    print(json.dumps(result.to_dict(), indent=2))

    _EMPTY_GUARD_MISSING = """
def last_k_total(marks, k):
    return sum(marks[-k:])
"""
    result2 = detect_mistakes(_EMPTY_GUARD_MISSING)
    print("\n=== No-guard Report ===")
    print(json.dumps(result2.to_dict(), indent=2))
