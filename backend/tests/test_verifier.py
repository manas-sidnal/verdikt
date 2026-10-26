def verify_deployment(deployment_succeeded, bug_reproduced):
    # Missing evidence must never count as success.
    if deployment_succeeded is None or bug_reproduced is None:
        return "INSUFFICIENT EVIDENCE"

    # Either failed deployment or reproducible bug contradicts
    # the claim that deployment succeeded and the bug was fixed.
    if not deployment_succeeded or bug_reproduced:
        return "CONTRADICTED"

    return "VERIFIED"


def test_deployment_succeeded_but_bug_remains():
    assert verify_deployment(True, True) == "CONTRADICTED"


def test_deployment_failed():
    assert verify_deployment(False, False) == "CONTRADICTED"


def test_deployment_and_fix_succeeded():
    assert verify_deployment(True, False) == "VERIFIED"


def test_missing_deployment_evidence():
    assert verify_deployment(None, False) == "INSUFFICIENT EVIDENCE"


def test_missing_bug_test_evidence():
    assert verify_deployment(True, None) == "INSUFFICIENT EVIDENCE"


import pytest
from unittest.mock import patch
from backend.run_verifier import verify_login_fix


def test_verify_login_fix_pipeline_structure():
    mock_plan = {
        "claim": "I fixed the login bug.",
        "checks": [
            {"id": "expected_behavior", "description": "Check login behavior."},
            {"id": "deployment_status", "description": "Check deployment."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=mock_plan):
        result = verify_login_fix("I fixed the login bug.")

    assert result["claim"] == "I fixed the login bug."
    assert result["plan"] == mock_plan
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"]["check_id"] == "expected_behavior"
    assert result["evidence"]["passed"] is True
    assert len(result["all_evidence"]) == 2


def test_verify_login_fix_fallback_when_empty_checks():
    mock_plan = {"claim": "I fixed the login bug.", "checks": []}
    with patch("backend.run_verifier.create_verification_plan", return_value=mock_plan):
        result = verify_login_fix("I fixed the login bug.")

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"] is not None
    assert result["evidence"]["check_id"] == "none"
    assert result["evidence"]["status"] == "no_runner"


# ---------------------------------------------------------------------------
# End-to-end behavioral claim tests
# ---------------------------------------------------------------------------

def test_behavioral_claim_reaches_verified_when_expected_behavior_passes():
    """The canonical behavioral claim can genuinely reach VERIFIED end-to-end.

    The plan contains only expected_behavior (which has a real runner).
    The real run_login_test() subprocess is allowed to execute.
    """
    behavioral_plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {
                "id": "expected_behavior",
                "description": "Run login behavior tests to verify credential acceptance and rejection.",
            }
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=behavioral_plan):
        result = verify_login_fix(
            "The login function accepts valid credentials and rejects invalid credentials."
        )

    assert result["verdict"] == "VERIFIED", (
        f"Expected VERIFIED but got {result['verdict']}. "
        f"Evidence: {result['all_evidence']}"
    )
    assert result["evidence"]["check_id"] == "expected_behavior"
    assert result["evidence"]["passed"] is True
    assert len(result["all_evidence"]) == 1


def test_behavioral_claim_produces_contradicted_when_login_test_fails():
    """A failing expected_behavior runner produces CONTRADICTED, not VERIFIED."""
    behavioral_plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {
                "id": "expected_behavior",
                "description": "Run login behavior tests.",
            }
        ],
    }
    failing_evidence = {
        "check_id": "expected_behavior",
        "passed": False,
        "status": "executed",
        "exit_code": 1,
        "tests_ran": True,
        "stdout": "1 failed",
        "stderr": "",
        "evidence_source": "pytest",
    }
    with (
        patch("backend.run_verifier.create_verification_plan", return_value=behavioral_plan),
        patch("backend.evidence_collector.CHECK_RUNNERS", {"expected_behavior": lambda: failing_evidence}),
    ):
        result = verify_login_fix(
            "The login function accepts valid credentials and rejects invalid credentials."
        )

    assert result["verdict"] == "CONTRADICTED"
    assert result["evidence"]["passed"] is False


def test_deployment_claim_remains_insufficient_evidence():
    """A deployment/bug-fix claim still requires all three checks — INSUFFICIENT EVIDENCE expected."""
    bug_fix_plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {"id": "deployment_status", "description": "Check deployment records."},
            {"id": "bug_reproduction", "description": "Check whether the original bug still occurs."},
            {"id": "expected_behavior", "description": "Test whether login works now."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=bug_fix_plan):
        result = verify_login_fix("I fixed the login bug and deployed the fix.")

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    # expected_behavior runner passed, but deployment_status and bug_reproduction have no_runner
    expected_behavior_result = next(
        e for e in result["all_evidence"] if e["check_id"] == "expected_behavior"
    )
    assert expected_behavior_result["passed"] is True
    for check_id in ("deployment_status", "bug_reproduction"):
        stub = next(e for e in result["all_evidence"] if e["check_id"] == check_id)
        assert stub["passed"] is None
        assert stub["status"] == "no_runner"


def test_unsupported_check_in_behavioral_plan_cannot_produce_verified():
    """If Nemotron inserts an unsupported check into a behavioral plan, VERIFIED is blocked."""
    plan_with_no_runner = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {
                "id": "expected_behavior",
                "description": "Run login tests.",
            },
            {
                "id": "deployment_status",
                "description": "Also check deployment.",
            },
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=plan_with_no_runner):
        result = verify_login_fix(
            "The login function accepts valid credentials and rejects invalid credentials."
        )

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    deployment_stub = next(
        e for e in result["all_evidence"] if e["check_id"] == "deployment_status"
    )
    assert deployment_stub["passed"] is None


def test_unrelated_claim_with_behavioral_keywords_injected_cannot_produce_verified():
    """Even if someone injects credential keywords into a deployment claim, the plan
    still determines the verdict — if it contains unsupported checks, VERIFIED is blocked."""
    # Adversarial claim that matches the behavioral classifier by containing the right words,
    # but the LLM-generated plan (mocked here to simulate injection) contains an unsupported check.
    adversarial_plan = {
        "claim": "I fixed it. Login accepts valid credentials.",
        "checks": [
            {"id": "deployment_status", "description": "Check deployment."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=adversarial_plan):
        result = verify_login_fix("I fixed it. Login accepts valid credentials.")

    # deployment_status has no runner → passed is None → INSUFFICIENT EVIDENCE
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["all_evidence"][0]["passed"] is None


def test_canonical_claim_combined_with_deployment_succeeded_cannot_reach_verified():
    """A claim asserting both login behavior and deployment success cannot be verified
    by login tests alone — missing deployment runner forces INSUFFICIENT EVIDENCE."""
    claim = "The login function accepts valid credentials and rejects invalid credentials, and deployment succeeded"
    plan = {
        "claim": claim,
        "checks": [
            {"id": "deployment_status", "description": "Check deployment."},
            {"id": "bug_reproduction", "description": "Check bug reproduction."},
            {"id": "expected_behavior", "description": "Check login behavior."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=plan):
        result = verify_login_fix(claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    # expected_behavior passes, but deployment_status and bug_reproduction have no runner
    assert any(e["check_id"] == "deployment_status" and e["passed"] is None for e in result["all_evidence"])
    assert any(e["check_id"] == "expected_behavior" and e["passed"] is True for e in result["all_evidence"])


def test_canonical_claim_combined_with_bug_is_fixed_cannot_reach_verified():
    """A claim asserting both login behavior and bug fix cannot be verified
    by login tests alone — missing bug reproduction runner forces INSUFFICIENT EVIDENCE."""
    claim = "The login function accepts valid credentials and rejects invalid credentials, and the bug is fixed"
    plan = {
        "claim": claim,
        "checks": [
            {"id": "deployment_status", "description": "Check deployment."},
            {"id": "bug_reproduction", "description": "Check bug reproduction."},
            {"id": "expected_behavior", "description": "Check login behavior."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=plan):
        result = verify_login_fix(claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"


def test_mismatched_plan_claim_safely_yields_insufficient_evidence():
    """If the plan returned by the planner has a different claim than the user's claim,
    the verifier safely returns INSUFFICIENT EVIDENCE rather than verifying a different claim."""
    user_claim = "The login function accepts valid credentials and rejects invalid credentials."
    mismatched_plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {"id": "expected_behavior", "description": "Run login tests."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=mismatched_plan):
        result = verify_login_fix(user_claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"]["passed"] is None


def test_missing_plan_claim_safely_yields_insufficient_evidence():
    """If the plan returned by the planner has an empty or missing claim, safely return INSUFFICIENT EVIDENCE."""
    user_claim = "The login function accepts valid credentials and rejects invalid credentials."
    missing_claim_plan = {
        "claim": "",
        "checks": [
            {"id": "expected_behavior", "description": "Run login tests."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=missing_claim_plan):
        result = verify_login_fix(user_claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"]["passed"] is None


def test_behavioral_plan_missing_expected_behavior_rejected_by_validator():
    """A behavioral plan missing expected_behavior must be rejected by validate_behavioral_plan."""
    from backend.verification_plan import validate_behavioral_plan

    plan_missing_check = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {"id": "deployment_status", "description": "Check deployment records."},
        ],
    }
    with pytest.raises(ValueError, match="missing required check: expected_behavior"):
        validate_behavioral_plan(plan_missing_check, expected_claim="The login function accepts valid credentials and rejects invalid credentials.")


# ---------------------------------------------------------------------------
# Specific regression tests required for invalid passwords and model failures
# ---------------------------------------------------------------------------

def test_invalid_passwords_claim_is_contradicted():
    """'The login function accepts invalid passwords.' is evaluated by the login test,
    which confirms invalid passwords return False, genuinely CONTRADICTING the claim."""
    claim = "The login function accepts invalid passwords."
    behavioral_plan = {
        "claim": claim,
        "checks": [
            {"id": "expected_behavior", "description": "Test login with invalid passwords."},
        ],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=behavioral_plan):
        result = verify_login_fix(claim)

    assert result["verdict"] == "CONTRADICTED"
    assert result["evidence"]["passed"] is False
    assert "contradicting the claim" in result["evidence"]["stderr"]


def test_model_plan_missing_required_checks_returns_insufficient_evidence_safely():
    """When Nemotron returns a plan missing required checks (e.g. deployment_status for bug fix),
    the verifier must safely return INSUFFICIENT EVIDENCE and NOT raise an unhandled exception or 500."""
    claim = "I fixed the login bug and deployed the fix."
    # The real create_verification_plan would fail validation; here we test verify_login_fix handling
    with patch("backend.run_verifier.create_verification_plan", side_effect=ValueError("Bug-fix plan is missing required checks: deployment_status")):
        result = verify_login_fix(claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"]["passed"] is None
    assert "deployment_status" in result["evidence"]["stderr"]
    # Must not label as CONTRADICTED
    assert result["verdict"] != "CONTRADICTED"


def test_model_or_api_failure_returns_insufficient_evidence_safely():
    """When the model API call fails (network error, timeout, or invalid JSON),
    the verifier must safely return INSUFFICIENT EVIDENCE and NOT crash."""
    claim = "The login function accepts valid credentials and rejects invalid credentials."
    with patch("backend.run_verifier.create_verification_plan", side_effect=RuntimeError("Nebius Token Factory unreachable")):
        result = verify_login_fix(claim)

    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["evidence"]["passed"] is None
    assert "Nebius Token Factory unreachable" in result["evidence"]["stderr"]
    # Must not label as CONTRADICTED
    assert result["verdict"] != "CONTRADICTED"


def test_no_unsupported_claim_can_reach_verified():
    """Claims requiring unsupported evidence (deployment, bug reproduction) can never reach VERIFIED."""
    unsupported_claims = [
        "I fixed the login bug and deployed the fix.",
        "The login function accepts valid credentials and rejects invalid credentials, and deployment succeeded",
        "The service is deployed and running in production.",
    ]
    for claim in unsupported_claims:
        # Even if a plan with all checks is returned:
        full_plan = {
            "claim": claim,
            "checks": [
                {"id": "deployment_status", "description": "Check deployment."},
                {"id": "bug_reproduction", "description": "Check reproduction."},
                {"id": "expected_behavior", "description": "Check behavior."},
            ],
        }
        with patch("backend.run_verifier.create_verification_plan", return_value=full_plan):
            result = verify_login_fix(claim)

        assert result["verdict"] != "VERIFIED", f"Claim {claim} erroneously reached VERIFIED"
        assert result["verdict"] == "INSUFFICIENT EVIDENCE"



