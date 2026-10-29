"""
Evidence collector for Verdikt.

Safety note: CHECK_RUNNERS is a fixed allowlist of trusted Python functions.
We never execute check IDs, file paths, shell strings, URLs, or any other
instruction supplied by Nemotron.  Only IDs that exist as keys in
CHECK_RUNNERS can dispatch to a real runner.
"""
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Individual runner functions
# ---------------------------------------------------------------------------

def run_login_test():
    """Run the login behavior test and capture its actual result.

    Kept as a standalone function for backward compatibility with existing
    tests and developer scripts.
    """
    try:
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
    except subprocess.TimeoutExpired:
        return {
            "check_id": "expected_behavior",
            "passed": None,
            "status": "timeout",
            "exit_code": None,
            "tests_ran": False,
            "stdout": "",
            "stderr": "Runner timed out.",
            "evidence_source": "pytest",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "check_id": "expected_behavior",
            "passed": None,
            "status": "runner_error",
            "exit_code": None,
            "tests_ran": False,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "evidence_source": "pytest",
        }

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = f"{stdout}\n{stderr}"

    passed_match = re.search(r"\b(\d+)\s+passed\b", stdout)
    failed_match = re.search(r"\b(\d+)\s+failed\b", stdout)
    error_match = re.search(r"\b(\d+)\s+error(s)?\b", stdout)

    is_collection_error = bool(
        "error collecting" in combined.lower()
        or "errors during collection" in combined.lower()
        or "collection error" in combined.lower()
        or "during collection" in combined.lower()
        or "syntaxerror" in combined.lower()
        or "importerror" in combined.lower()
        or "modulenotfounderror" in combined.lower()
        or (error_match and not failed_match and not passed_match)
    )

    if result.returncode == 0 and passed_match and not is_collection_error:
        tests_ran = True
        passed = True
        status = "executed"
    elif result.returncode == 1 and failed_match and not is_collection_error:
        tests_ran = True
        passed = False
        status = "executed"
    else:
        tests_ran = False
        passed = None
        if is_collection_error:
            status = "collection_error"
        elif result.returncode == 5:
            status = "no_tests_collected"
        else:
            status = "infrastructure_error"

    return {
        "check_id": "expected_behavior",
        "passed": passed,
        "status": status,
        "exit_code": result.returncode,
        "tests_ran": tests_ran,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "evidence_source": "pytest",
    }


def evaluate_login_test_against_claim(claim: str, evidence: dict) -> dict:
    """Evaluate whether the login test execution supports or contradicts the claim.

    The login behavior test (test_login_behavior.py) verifies:
      1. Valid credentials succeed (return True).
      2. Invalid passwords are rejected (return False).
      3. Unknown users are rejected (return False).

    Therefore:
    - If the claim asserts that invalid passwords or invalid credentials are ACCEPTED:
      The test result (which confirms they are REJECTED) CONTRADICTS the claim -> passed: False.
    - If the claim asserts that valid credentials or valid passwords are REJECTED:
      The test result (which confirms they are ACCEPTED) CONTRADICTS the claim -> passed: False.
    - If the claim asserts that valid credentials are accepted and/or invalid credentials/passwords are rejected:
      The test result (passed: True) SUPPORTS the claim -> passed: True.
    - If the test execution itself failed (passed: False):
      The check failed -> passed: False.
    """
    if not isinstance(claim, str) or not claim.strip():
        return evidence

    # If the runner already failed or had no runner, preserve that state
    if evidence.get("passed") is not True:
        return evidence

    lower = claim.lower().strip()

    # Check if the claim asserts that invalid credentials or invalid passwords are accepted:
    # e.g. "The login function accepts invalid passwords", "accepts invalid credentials"
    asserts_invalid_accepted = bool(
        re.search(r"\b(accept|accepts|accepting|allow|allows)\b[^.]*\b(invalid\s+(password|credential)s?)\b", lower)
        and not re.search(r"\b(reject|rejects|rejecting|deny|denies|block|blocks)\b[^.]*\b(invalid\s+(password|credential)s?)\b", lower)
    )

    # Check if the claim asserts that valid credentials or valid passwords are rejected:
    # e.g. "The login function rejects valid credentials"
    asserts_valid_rejected = bool(
        re.search(r"\b(reject|rejects|rejecting|deny|denies|block|blocks)\b[^.]*\b(valid\s+(password|credential)s?)\b", lower)
        and not re.search(r"\b(accept|accepts|accepting|allow|allows)\b[^.]*\b(valid\s+(password|credential)s?)\b", lower)
    )

    if asserts_invalid_accepted:
        result = dict(evidence)
        result["passed"] = False
        result["stderr"] = (
            "Login test confirmed that invalid passwords/credentials are rejected, "
            "contradicting the claim that they are accepted."
        )
        return result

    if asserts_valid_rejected:
        result = dict(evidence)
        result["passed"] = False
        result["stderr"] = (
            "Login test confirmed that valid credentials are accepted, "
            "contradicting the claim that they are rejected."
        )
        return result

    return evidence


def _no_runner(check_id: str) -> dict:
    """Return a structured stub for a check that has no real implementation."""
    return {
        "check_id": check_id,
        "passed": None,
        "status": "no_runner",
        "exit_code": None,
        "tests_ran": False,
        "stdout": "",
        "stderr": "",
        "evidence_source": "none",
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Maps each allowlisted check ID to a zero-argument callable that returns an
# evidence dict.  IDs that have no genuine implementation are absent from this
# mapping; collect_plan_evidence() returns a "no_runner" stub for them.
#
# Do not add entries here that call shell commands, evaluate arbitrary code,
# fetch URLs, or otherwise execute input that originated from Nemotron.
CHECK_RUNNERS: dict = {
    "expected_behavior": run_login_test,
    # "bug_reproduction":   run_reproduction_test,   # not yet implemented
    # "deployment_status":  check_deployment_status, # not yet implemented
}


# ---------------------------------------------------------------------------
# Plan-driven collection
# ---------------------------------------------------------------------------

def collect_plan_evidence(plan: dict) -> list:
    """Collect evidence for every check requested in a validated plan.

    Iterates over plan["checks"] in order.  For each check:
    - If the check ID has a registered runner, call it and capture the result.
    - If the runner raises or times out, record the failure safely without
      treating it as a passing check.
    - If no runner is registered, return a "no_runner" stub with passed=None.

    Args:
        plan: A validated verification plan dict produced by
              create_verification_plan().

    Returns:
        A list of evidence dicts, one per check in the plan, in the same order.
    """
    results = []
    claim = plan.get("claim", "") if isinstance(plan, dict) else ""
    for check in plan.get("checks", []):
        check_id = check.get("id", "")
        runner = CHECK_RUNNERS.get(check_id)

        if runner is None:
            results.append(_no_runner(check_id))
            continue

        try:
            evidence = runner()
            # Ensure the returned dict carries the correct check_id.
            evidence = dict(evidence)
            evidence["check_id"] = check_id
            if check_id == "expected_behavior" and claim:
                evidence = evaluate_login_test_against_claim(claim, evidence)
            results.append(evidence)
        except subprocess.TimeoutExpired:
            results.append({
                "check_id": check_id,
                "passed": None,
                "status": "timeout",
                "exit_code": None,
                "tests_ran": False,
                "stdout": "",
                "stderr": "Runner timed out.",
                "evidence_source": "pytest",
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "check_id": check_id,
                "passed": None,
                "status": "runner_error",
                "exit_code": None,
                "tests_ran": False,
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
                "evidence_source": "pytest",
            })

    return results
