# Tutor Randomized Question Plugin & Open edX XBlock

A Tutor plugin and companion Open edX XBlock for advanced single- and multi-select questions with pool-based subset sampling, position randomization, and visual piecewise case grading.

---

## Features

1. **Answer Position Randomization**: Shuffles choice positions deterministically per student attempt (seed-stabilized across page reloads).
2. **Pool-Based Subset Sampling**:
   - Correct answers pool $C$ and Incorrect answers pool $I$.
   - Configurable total answers count $t$, where $2 \le t \le |C| + |I|$.
   - Configurable correct answers count $c$, where $1 \le c \le |C|$ and $(t - c) \le |I|$.
3. **Custom Piecewise Grading Function $g(x)$**:
   - Depends on the count of correctly guessed answers ($x$) and wrong selections ($w$).
   - Strict default fail rules ($g(x) = 0$):
     1. At least one wrong answer was selected ($w > 0$).
     2. Not all displayed correct answers were selected ($x < c$).
   - Configurable piecewise cases (e.g. 100% for $x = c$, 50% for $x = c - 1$, custom condition expressions).
4. **User-Friendly Studio Authoring UI**:
   - Visual lists for Pool $C$ and Pool $I$ management with live duplicate and disjoint pool checks.
   - Live constraint validation with dynamic error feedback.
   - Interactive table for defining grading cases, scoring percentages, and feedback messages.
5. **Open edX Standard Grading Controls**:
   - Problem points / weight.
   - Maximum allowed attempts with reset/reseed support and attempt exhaustion locking.
   - Show Correctness Modes (`always`, `past_due`, `never`).
   - Native LMS grade publication (`runtime.publish(..., "grade", ...)`).

---

## Directory Structure

```text
tutor-randomized-question/
├── tutor_randomized_question/
│   ├── __init__.py
│   └── plugin.py               # Tutor v1 plugin hooks & Dockerfile patches
├── randomized_question_xblock/
│   ├── __init__.py
│   ├── engine.py               # Pool sampling, validation & case grading engine
│   ├── models.py               # Strongly-typed Pydantic v2 schemas & validators
│   ├── xblock.py               # XBlock implementation, Studio/LMS handlers
│   └── static/
│       ├── css/                # Studio & Student styles
│       ├── js/                 # Studio & Student interactive logic
│       └── html/               # Studio & Student HTML templates
├── tests/
│   ├── artifacts/              # Video recordings & test artifacts
│   ├── integration/
│   │   ├── server.py           # Integration test server & XBlock runtime simulator
│   │   ├── test_playwright_e2e.py  # Parameterized Playwright test suite
│   │   └── record_e2e_video.py # Full visual workflow MP4 video recorder
│   ├── test_engine.py          # Math constraints, sampling & determinism tests
│   ├── test_grading_cases.py   # Piecewise grading & fail conditions tests
│   ├── test_models.py          # Pydantic model validations & field tests
│   ├── test_xblock.py          # XBlock lifecycle & handler tests
│   └── test_tutor_plugin.py    # Tutor plugin config & patch tests
├── Makefile                    # Automation: lint, typecheck, test, format
├── pyproject.toml              # Build config & linter settings
├── setup.py                    # Packaging & entry points
└── README.md
```

---

## Installation & Deployment

### 1. Install as a Tutor Plugin
In your Tutor environment:

```bash
pip install -e /path/to/tutor-randomized-question
tutor plugins enable randomized_question
```

### 2. Build Open edX Docker Image
Rebuild the LMS/CMS Docker images to bundle the XBlock:

```bash
tutor images build openedx
tutor local start -d
```

### 3. Enable in Course Advanced Settings
In Open edX Studio:
1. Navigate to **Settings > Advanced Settings**.
2. Add `"randomized_question"` to the **Advanced Module List** (`[..., "randomized_question"]`).
3. Save changes.
4. In any Unit, select **Add New Component > Advanced > Randomized Multi-Choice Question**.

---

## Quality Gates & Verification

Run all static checks and automated tests via Makefile:

```bash
make check      # Runs ruff check -> mypy -> pytest
```

### Record E2E Video Walkthrough
To record a fresh end-to-end MP4 video of all teacher and student scenarios:

```bash
python tests/integration/record_e2e_video.py
```
Output: `tests/artifacts/randomized_question_e2e.mp4`

---

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3). See the [LICENSE](LICENSE) file for details.

