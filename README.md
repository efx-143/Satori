<div align="center">

# 🥋 Debug Dojo

### *The AI-powered EdTech platform where coders sharpen their skills through intelligent, sandboxed challenges.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Sandboxed-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=for-the-badge)](https://sqlalchemy.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

> **Debug Dojo** is a full-stack coding practice platform that runs learner-submitted Python code inside a hardened Docker sandbox, tracks concept mastery, and detects structural coding mistakes using AST analysis — all in real-time.

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Concept Mastery Tracking** | Per-learner mastery scores updated after every submission |
| 🐳 **Hardened Sandbox** | Docker + seccomp + rlimits — zero network, read-only FS, no fork bombs |
| 🔍 **AST Mistake Detection** | 5-category taxonomy: off-by-one, print-not-return, mutates-input, and more |
| 🎯 **Smart Test Runner** | 4 canonical outcomes: `passed` · `wrong_output` · `runtime_error` · `timeout` |
| 🔒 **Hidden Test Secrecy** | Hidden test inputs/outputs/tracebacks are **never** leaked to the learner |
| 🏆 **XP & Streaks** | Gamified learning with XP points and daily streak tracking |

---

## 🏗️ Project Structure

```
debug-dojo/
└── backend/
    ├── app/
    │   ├── __init__.py              # Flask app factory
    │   ├── config.py                # Dev / Test / Prod config
    │   ├── models/
    │   │   ├── learner.py           # User profile + gamification
    │   │   ├── concept_mastery.py   # Per-concept mastery scores
    │   │   ├── challenge.py         # Problem data + starter code
    │   │   ├── test_case.py         # Visible & hidden test cases
    │   │   └── submission.py        # Submission history + mistake tags
    │   ├── services/
    │   │   └── test_runner.py       # Host-side sandbox orchestrator
    │   └── utils/
    │       └── mistake_detector.py  # AST-based mistake taxonomy engine
    ├── sandbox/
    │   ├── Dockerfile               # Hardened Python 3.11 image (nobody UID)
    │   ├── seccomp_profile.json     # Custom syscall whitelist
    │   └── runner_entrypoint.py    # In-container execution engine
    ├── seed/
    │   └── challenges.json          # 10 Python challenges seed data
    ├── tests/
    │   ├── test_runner_unit.py      # 23 unit tests (no Docker needed) ✅
    │   └── test_sandbox_redteam.py  # Full red-team security tests
    ├── seed_db.py                   # Idempotent database seeder
    ├── build_sandbox.sh             # One-command Docker image builder
    └── requirements.txt
```

---

## 🗄️ Database Schema

```
Learner ──< ConceptMastery
   │
   └──< Submission >── Challenge ──< TestCase
```

| Model | Key Fields |
|---|---|
| `Learner` | `id`, `username`, `email`, `xp_points`, `streak_days` |
| `ConceptMastery` | `learner_id`, `concept_tag`, `mastery_score`, `attempts` |
| `Challenge` | `id` (slug), `title`, `difficulty`, `concept_tags` (JSON), `starter_code` |
| `TestCase` | `input_args` (JSON), `expected_output` (JSON), `is_hidden` |
| `Submission` | `code`, `outcome`, `mistake_tags` (JSON), `xp_awarded` |

---

## 🐳 Sandbox Security Model

The sandbox enforces **7 layers of isolation**:

```
┌─────────────────────────────────────────────────────┐
│  Docker --network none          (zero network)       │
│  Docker --read-only             (no FS writes)       │
│  Docker --memory 128m           (RAM cap)            │
│  Docker --pids-limit 64         (no fork bombs)      │
│  Docker --cap-drop ALL          (no capabilities)    │
│  seccomp_profile.json           (syscall whitelist)  │
│  rlimits inside container       (belt + suspenders)  │
│  _RestrictedImporter            (no os/socket/etc)   │
│  Safe __builtins__ whitelist    (no exec hijacking)  │
└─────────────────────────────────────────────────────┘
```

### Blocked Threats
- 🚫 Network requests (`socket`, `urllib`, `http`, `requests`)
- 🚫 Process spawning (`os.fork`, `subprocess`, `multiprocessing`)
- 🚫 File system access (`/etc/passwd`, env vars, parent dirs)
- 🚫 Memory bombs (128 MiB hard cap)
- 🚫 Infinite loops (per-test `SIGALRM` timeout)
- 🚫 Privilege escalation (`--no-new-privileges`, UID 65534)

---

## 🔬 Mistake Taxonomy

The `mistake_detector.py` module uses Python's `ast` module to detect 5 structural mistake categories:

| Tag | What It Catches |
|---|---|
| `off_by_one` | `range(1, n)`, `range(..., n-1)`, slice ending at `x-1` |
| `unhandled_short_input` | Direct `param[0]` access without an empty/length guard |
| `print_not_return` | Functions that `print()` but never `return` a value |
| `boundary_comparison` | `> 40` instead of `>= 40`, `> 0` instead of `>= 1` |
| `mutates_input` | `.append()`, `.pop()`, `.sort()`, `param[i] = x`, `param +=` |

```python
from app.utils.mistake_detector import detect_mistakes

result = detect_mistakes("""
def count_passes(marks):
    for i in range(1, len(marks)):   # off_by_one
        if marks[i] > 40:            # boundary_comparison
            count += 1
    print(count)                     # print_not_return
    marks.append(0)                  # mutates_input
""")

print(result.tags)
# → ['off_by_one', 'unhandled_short_input', 'print_not_return',
#    'boundary_comparison', 'mutates_input']
```

---

## 📦 Challenge Dataset

10 Python challenges seeded out of the box:

| Challenge | Difficulty | Concepts |
|---|---|---|
| `last-k-total` | Easy | lists, slicing, arithmetic |
| `count-passes` | Easy | lists, loops, conditionals |
| `first-n-squares` | Easy | lists, loops, arithmetic |
| `middle-three` | Medium | lists, slicing, indexing |
| `sum-of-evens` | Easy | lists, loops, conditionals |
| `reverse-words` | Easy | strings, lists, slicing |
| `remove-duplicates` | Medium | lists, dicts, loops |
| `flatten-one-level` | Medium | lists, loops, comprehensions |
| `binary-search` | Hard | searching, loops, indexing |
| `group-by-key` | Hard | dicts, lists, loops |

Each challenge has **3 visible + 7 hidden test cases** covering edge cases (empty inputs, negatives, boundary values, etc.).

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Docker 20+

### 1. Clone & Install

```bash
git clone https://github.com/efx-143/Satori.git
cd Satori/backend
pip install -r requirements.txt
```

### 2. Seed the Database

```bash
python seed_db.py
```

### 3. Build the Sandbox Image

```bash
# First, add yourself to the docker group (one-time setup):
sudo usermod -aG docker $USER
# Log out and back in, then:

chmod +x build_sandbox.sh
./build_sandbox.sh
```

### 4. Run Tests

```bash
# Unit tests (no Docker required):
python -m pytest tests/test_runner_unit.py -v

# Red-team security tests (requires sandbox image):
python -m pytest tests/test_sandbox_redteam.py -v
```

### 5. Use the Test Runner

```python
from app.services.test_runner import get_runner

result = get_runner().run(
    code="def last_k_total(marks, k): return sum(marks[-k:] or marks)",
    fn_name="last_k_total",
    test_cases=[
        {"test_id": "tc1", "input_args": [[10,20,30,40,50], 3],
         "expected_output": 120, "is_hidden": False},
        {"test_id": "tc2", "input_args": [[], 3],
         "expected_output": 0, "is_hidden": True},  # hidden – no leakage
    ],
)

print(result.to_dict())
```

---

## 🧪 Test Coverage

```
Unit Tests:    23 passed ✅  (test_runner_unit.py   — no Docker needed)
Red-Team:      18 tests  🐳  (test_sandbox_redteam.py — requires Docker image)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask 3 · SQLAlchemy 2 |
| Database | SQLite (dev) · PostgreSQL-ready (prod) |
| Sandbox | Docker · Linux seccomp · POSIX rlimits · SIGALRM |
| Analysis | Python `ast` module · Regex |
| Testing | pytest |

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for Debug Dojo Hackathon**

</div>
