"""Pre-flight check. Run before making any change: `python docs/development/init.py`.

Verifies the harness structure is intact and, if a test suite exists, that it passes.
Exits non-zero on any failure so the caller stops instead of proceeding on broken state.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root

REQUIRED_FILES = [
    "CLAUDE.md",
    "docs/development/memory.md",
    "docs/development/roles/planner.md",
    "docs/development/roles/builder.md",
    "docs/development/roles/reviewer.md",
    "docs/development/workflows/generate_strategy.md",
    "docs/development/workflows/backtest_strategy.md",
    "docs/development/workflows/validate_strategy.md",
]


def check_required_files():
    errors = []
    for rel_path in REQUIRED_FILES:
        path = ROOT / rel_path
        if not path.is_file():
            errors.append(f"missing required file: {rel_path}")
        elif path.stat().st_size == 0:
            errors.append(f"required file is empty: {rel_path}")
    return errors


def run_tests_if_present():
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        print("[init] no tests/ directory yet - skipping test run")
        return []

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        return [f"test suite failed with exit code {result.returncode}"]
    return []


def main():
    errors = check_required_files()
    errors += run_tests_if_present()

    if errors:
        print("[init] FAILED:")
        for err in errors:
            print(f"  - {err}")
        print("[init] Stop. Fix the above before making any change.")
        sys.exit(1)

    print("[init] OK - harness structure intact.")
    sys.exit(0)


if __name__ == "__main__":
    main()
