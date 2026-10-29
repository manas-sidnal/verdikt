"""
Tests for backend/evidence_collector.py (collect_plan_evidence, CHECK_RUNNERS)
and backend/verdict_engine.py (evaluate_evidence_list).

No real Nebius API key or network connection is required.
External subprocess calls are mocked where needed.
"""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from evidence_collector import (
    CHECK_RUNNERS,
    _no_runner,
    collect_plan_evidence,
    run_login_test,
)
from verdict_engine import evaluate_evidence_list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(*check_ids):
    """Build a minimal plan dict with the requested check IDs."""
    return {
        "claim": "Test claim.",
        "checks": [{"id": cid, "description": f"Check {cid}."} for cid in check_ids],
    }


def _passing_evidence(check_id="expected_behavior"):
    return {
        "check_id": check_id,
        "passed": True,
        "status": "executed",
        "exit_code": 0,
        "tests_ran": True,
        "stdout": "3 passed",
        "stderr": "",
        "evidence_source": "pytest",
    }


def _failing_evidence(check_id="expected_behavior"):
    return {
        "check_id": check_id,
        "passed": False,
        "status": "executed",
        "exit_code": 1,
        "tests_ran": False,
        "stdout": "1 failed",
        "stderr": "",
        "evidence_source": "pytest",
    }


# ---------------------------------------------------------------------------
# _no_runner
# ---------------------------------------------------------------------------

def test_no_runner_has_passed_none():
    result = _no_runner("deployment_status")
    assert result["passed"] is None


def test_no_runner_has_correct_check_id():
    result = _no_runner("bug_reproduction")
    assert result["check_id"] == "bug_reproduction"


def test_no_runner_status_is_no_runner():
    result = _no_runner("deployment_status")
    assert result["status"] == "no_runner"


# ---------------------------------------------------------------------------
# CHECK_RUNNERS registry
# ---------------------------------------------------------------------------

def test_expected_behavior_is_registered():
    assert "expected_behavior" in CHECK_RUNNERS


def test_deployment_status_not_registered():
    """deployment_status has no real runner yet."""
    assert "deployment_status" not in CHECK_RUNNERS


def test_bug_reproduction_not_registered():
    """bug_reproduction has no real runner yet."""
    assert "bug_reproduction" not in CHECK_RUNNERS


# ---------------------------------------------------------------------------
# collect_plan_evidence — routing
# ---------------------------------------------------------------------------

def test_unsupported_check_returns_no_runner_stub():
    plan = _make_plan("deployment_status")
    results = collect_plan_evidence(plan)
    assert len(results) == 1
    assert results[0]["check_id"] == "deployment_status"
    assert results[0]["passed"] is None
    assert results[0]["status"] == "no_runner"


def test_mixed_plan_produces_one_result_per_check():
    """One supported + two unsupported checks → three results."""
    plan = _make_plan("deployment_status", "expected_behavior", "bug_reproduction")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: _passing_evidence("expected_behavior")},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    assert len(results) == 3
    check_ids = [r["check_id"] for r in results]
    assert check_ids == ["deployment_status", "expected_behavior", "bug_reproduction"]


def test_supported_check_passes():
    plan = _make_plan("expected_behavior")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: _passing_evidence("expected_behavior")},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    assert results[0]["passed"] is True
    assert results[0]["status"] == "executed"


def test_supported_check_fails():
    plan = _make_plan("expected_behavior")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: _failing_evidence("expected_behavior")},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    assert results[0]["passed"] is False


def test_runner_exception_is_captured_as_failure():
    def _boom():
        raise RuntimeError("something went wrong")

    plan = _make_plan("expected_behavior")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": _boom},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    assert len(results) == 1
    result = results[0]
    assert result["passed"] is None
    assert result["status"] == "runner_error"
    assert "RuntimeError" in result["stderr"]
    assert evaluate_evidence_list(results) == "INSUFFICIENT EVIDENCE"


def test_runner_timeout_is_captured_as_failure():
    def _slow():
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=30)

    plan = _make_plan("expected_behavior")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": _slow},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    assert len(results) == 1
    result = results[0]
    assert result["passed"] is None
    assert result["status"] == "timeout"
    assert evaluate_evidence_list(results) == "INSUFFICIENT EVIDENCE"


def test_empty_plan_returns_empty_list():
    """A plan with no checks produces an empty evidence list."""
    plan = {"claim": "Some claim.", "checks": []}
    results = collect_plan_evidence(plan)
    assert results == []


# ---------------------------------------------------------------------------
# evaluate_evidence_list
# ---------------------------------------------------------------------------

def test_all_pass_gives_verified():
    evidence = [
        {"check_id": "expected_behavior", "passed": True},
        {"check_id": "bug_reproduction", "passed": True},
    ]
    assert evaluate_evidence_list(evidence) == "VERIFIED"


def test_one_fail_gives_contradicted():
    evidence = [
        {"check_id": "expected_behavior", "passed": False},
        {"check_id": "deployment_status", "passed": None},
    ]
    assert evaluate_evidence_list(evidence) == "CONTRADICTED"


def test_fail_takes_priority_over_none():
    """A contradicting check should beat a missing-evidence check."""
    evidence = [
        {"check_id": "deployment_status", "passed": None},
        {"check_id": "expected_behavior", "passed": False},
    ]
    assert evaluate_evidence_list(evidence) == "CONTRADICTED"


def test_missing_evidence_gives_insufficient():
    evidence = [
        {"check_id": "expected_behavior", "passed": True},
        {"check_id": "deployment_status", "passed": None},
    ]
    assert evaluate_evidence_list(evidence) == "INSUFFICIENT EVIDENCE"


def test_empty_list_gives_insufficient():
    assert evaluate_evidence_list([]) == "INSUFFICIENT EVIDENCE"


def test_all_none_gives_insufficient():
    evidence = [
        {"check_id": "deployment_status", "passed": None},
        {"check_id": "bug_reproduction", "passed": None},
    ]
    assert evaluate_evidence_list(evidence) == "INSUFFICIENT EVIDENCE"


# ---------------------------------------------------------------------------
# Integration: mixed plan → verdict
# ---------------------------------------------------------------------------

def test_one_fail_others_unsupported_gives_contradicted():
    """CONTRADICTED if any check fails, even if others have no runner."""
    plan = _make_plan("expected_behavior", "deployment_status", "bug_reproduction")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: _failing_evidence("expected_behavior")},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    verdict = evaluate_evidence_list(results)
    assert verdict == "CONTRADICTED"


def test_one_pass_others_unsupported_gives_insufficient():
    """INSUFFICIENT EVIDENCE when some checks have no runner."""
    plan = _make_plan("expected_behavior", "deployment_status", "bug_reproduction")
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: _passing_evidence("expected_behavior")},
        clear=True,
    ):
        results = collect_plan_evidence(plan)
    verdict = evaluate_evidence_list(results)
    assert verdict == "INSUFFICIENT EVIDENCE"


def test_unregistered_or_malicious_check_id_is_not_executed():
    """Injected or unrecognized check IDs must never invoke a runner."""
    plan = {
        "claim": "I fixed it",
        "checks": [
            {"id": "rm -rf /; echo hack", "description": "malicious check command"}
        ],
    }
    results = collect_plan_evidence(plan)
    assert len(results) == 1
    assert results[0]["check_id"] == "rm -rf /; echo hack"
    assert results[0]["passed"] is None
    assert results[0]["status"] == "no_runner"


def test_real_run_login_test_executes():
    """Real run_login_test() runs pytest subprocess and parses output correctly."""
    evidence = run_login_test()
    assert evidence["check_id"] == "expected_behavior"
    assert evidence["passed"] is True
    assert evidence["status"] == "executed"
    assert evidence["exit_code"] == 0
    assert evidence["tests_ran"] is True
    assert "3 passed" in evidence["stdout"]
    assert evidence["evidence_source"] == "pytest"


def test_non_boolean_passed_value_yields_insufficient_evidence():
    """Any non-True passed value (string, zero, missing) cannot produce VERIFIED."""
    evidence_str = [{"check_id": "test", "passed": "pending"}]
    assert evaluate_evidence_list(evidence_str) == "INSUFFICIENT EVIDENCE"

    evidence_zero = [{"check_id": "test", "passed": 0}]
    assert evaluate_evidence_list(evidence_zero) == "INSUFFICIENT EVIDENCE"


# ---------------------------------------------------------------------------
# Regression tests for evidence status handling (Requirement 6)
# ---------------------------------------------------------------------------

def test_run_login_test_collection_error_produces_passed_none():
    """A pytest collection failure must produce passed: None and not CONTRADICTED."""
    fake_completed = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=2,
        stdout="ERROR collecting backend/tests/test_login_behavior.py\nSyntaxError: invalid syntax\n1 error in 0.05s",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_completed):
        evidence = run_login_test()

    assert evidence["check_id"] == "expected_behavior"
    assert evidence["passed"] is None
    assert evidence["status"] == "collection_error"
    assert evidence["tests_ran"] is False
    assert evidence["exit_code"] == 2
    assert evaluate_evidence_list([evidence]) == "INSUFFICIENT EVIDENCE"


def test_run_login_test_import_error_produces_passed_none():
    """Import / module errors during collection produce passed: None."""
    fake_completed = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=2,
        stdout="ERROR collecting backend/tests/test_login_behavior.py\nModuleNotFoundError: No module named 'login_app'\n1 error in 0.02s",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_completed):
        evidence = run_login_test()

    assert evidence["passed"] is None
    assert evidence["status"] == "collection_error"
    assert evidence["tests_ran"] is False
    assert evaluate_evidence_list([evidence]) == "INSUFFICIENT EVIDENCE"


def test_run_login_test_assertion_failure_produces_genuine_contradiction():
    """Completed tests with assertion failures produce passed: False and CONTRADICTED."""
    fake_completed = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=1,
        stdout="F..\n=== FAILURES ===\nFAILED test_login_behavior.py::test_invalid_password_is_rejected\n1 failed, 2 passed in 0.05s",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_completed):
        evidence = run_login_test()

    assert evidence["check_id"] == "expected_behavior"
    assert evidence["passed"] is False
    assert evidence["status"] == "executed"
    assert evidence["tests_ran"] is True
    assert evidence["exit_code"] == 1
    assert evaluate_evidence_list([evidence]) == "CONTRADICTED"


def test_run_login_test_handles_different_passed_counts():
    """run_login_test does not hardcode '3 passed' and recognizes any passing count."""
    fake_completed = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=0,
        stdout="..... [100%]\n5 passed in 0.08s",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_completed):
        evidence = run_login_test()

    assert evidence["passed"] is True
    assert evidence["status"] == "executed"
    assert evidence["tests_ran"] is True
    assert evaluate_evidence_list([evidence]) == "VERIFIED"


def test_mixture_of_inconclusive_and_contradictory_evidence_produces_contradicted():
    """Genuine contradiction takes precedence over inconclusive evidence."""
    evidence = [
        {"check_id": "check_timeout", "passed": None, "status": "timeout"},
        {"check_id": "check_failed", "passed": False, "status": "executed"},
        {"check_id": "check_error", "passed": None, "status": "runner_error"},
        {"check_id": "check_passed", "passed": True, "status": "executed"},
    ]
    assert evaluate_evidence_list(evidence) == "CONTRADICTED"


def test_mixture_of_inconclusive_and_passing_evidence_produces_insufficient_evidence():
    """Without genuine contradiction, missing/inconclusive evidence yields INSUFFICIENT EVIDENCE."""
    evidence = [
        {"check_id": "check_passed", "passed": True, "status": "executed"},
        {"check_id": "check_timeout", "passed": None, "status": "timeout"},
    ]
    assert evaluate_evidence_list(evidence) == "INSUFFICIENT EVIDENCE"


def test_invalid_passwords_claim_with_collection_failure_is_not_contradicted():
    """If the login check fails collection, 'accepts invalid passwords' is INSUFFICIENT EVIDENCE, not CONTRADICTED."""
    fake_collection_error = {
        "check_id": "expected_behavior",
        "passed": None,
        "status": "collection_error",
        "exit_code": 2,
        "tests_ran": False,
        "stdout": "ERROR collecting test_login_behavior.py",
        "stderr": "",
        "evidence_source": "pytest",
    }
    plan = {
        "claim": "The login function accepts invalid passwords.",
        "checks": [{"id": "expected_behavior", "description": "Run login behavior tests."}],
    }
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": lambda: fake_collection_error},
        clear=True,
    ):
        results = collect_plan_evidence(plan)

    assert len(results) == 1
    assert results[0]["passed"] is None
    assert evaluate_evidence_list(results) == "INSUFFICIENT EVIDENCE"


def test_invalid_passwords_claim_with_timeout_is_not_contradicted():
    """If the login check times out, 'accepts invalid passwords' is INSUFFICIENT EVIDENCE, not CONTRADICTED."""
    def _slow():
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=30)

    plan = {
        "claim": "The login function accepts invalid passwords.",
        "checks": [{"id": "expected_behavior", "description": "Run login behavior tests."}],
    }
    with patch.dict(
        "evidence_collector.CHECK_RUNNERS",
        {"expected_behavior": _slow},
        clear=True,
    ):
        results = collect_plan_evidence(plan)

    assert len(results) == 1
    assert results[0]["passed"] is None
    assert results[0]["status"] == "timeout"
    assert evaluate_evidence_list(results) == "INSUFFICIENT EVIDENCE"


