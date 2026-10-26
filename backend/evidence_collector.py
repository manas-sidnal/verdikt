import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_login_test():
    """Run the login behavior test and capture its actual result."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_login_behavior.py",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    tests_ran = "3 passed" in result.stdout

    return {
        "check_id": "expected_behavior",
        "passed": result.returncode == 0 and tests_ran,
        "exit_code": result.returncode,
        "tests_ran": tests_ran,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "evidence_source": "pytest",
    }
