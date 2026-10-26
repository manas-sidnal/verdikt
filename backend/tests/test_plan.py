import pytest

from verification_plan import (
    classify_claim,
    validate_behavioral_plan,
    validate_bug_fix_plan,
    validate_plan,
)


def test_valid_plan():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check whether deployment succeeded.",
            },
            {
                "id": "bug_reproduction",
                "description": "Test whether the login bug still occurs.",
            },
        ],
    }

    assert validate_plan(plan) is True


def test_missing_claim():
    plan = {
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment.",
            }
        ]
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_empty_checks():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_unsupported_check():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [
            {
                "id": "delete_database",
                "description": "Delete the database.",
            }
        ],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_missing_description():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [
            {"id": "deployment_status"}
        ],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)



def test_complete_bug_fix_plan():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment records.",
            },
            {
                "id": "bug_reproduction",
                "description": "Check whether the original bug existed.",
            },
            {
                "id": "expected_behavior",
                "description": "Test whether login works now.",
            },
        ],
    }

    assert validate_bug_fix_plan(plan) is True


def test_bug_fix_plan_missing_current_behavior_check():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment records.",
            },
            {
                "id": "bug_reproduction",
                "description": "Check whether the original bug existed.",
            },
        ],
    }

    with pytest.raises(ValueError, match="expected_behavior"):
        validate_bug_fix_plan(plan)


# ---------------------------------------------------------------------------
# classify_claim
# ---------------------------------------------------------------------------

from verification_plan import classify_claim


def test_canonical_behavioral_claim_is_classified_correctly():
    claim = "The login function accepts valid credentials and rejects invalid credentials."
    assert classify_claim(claim) == "behavioral"


def test_canonical_behavioral_claim_case_insensitive():
    claim = "THE LOGIN FUNCTION ACCEPTS VALID CREDENTIALS AND REJECTS INVALID CREDENTIALS."
    assert classify_claim(claim) == "behavioral"


def test_short_behavioral_variant_is_classified_correctly():
    """login + accept + reject + credential phrase set."""
    claim = "Login accepts valid credentials and rejects invalid ones."
    assert classify_claim(claim) == "behavioral"


def test_login_function_accept_variant_is_classified_correctly():
    """login function + accept + valid credential phrase set."""
    claim = "The login function will accept valid credentials only."
    assert classify_claim(claim) == "behavioral"


def test_bug_fix_claim_is_classified_as_bug_fix():
    claim = "I fixed the login bug and deployed the fix."
    assert classify_claim(claim) == "bug_fix"


def test_deployment_claim_is_classified_as_bug_fix():
    claim = "The service is deployed and running."
    assert classify_claim(claim) == "bug_fix"


def test_generic_claim_is_classified_as_bug_fix():
    claim = "The application is working correctly."
    assert classify_claim(claim) == "bug_fix"


def test_partial_login_keyword_alone_is_not_behavioral():
    """Just containing 'login' is not enough — avoids false positives."""
    claim = "I fixed the login bug."
    assert classify_claim(claim) == "bug_fix"


def test_non_string_claim_defaults_to_bug_fix():
    assert classify_claim(None) == "bug_fix"  # type: ignore[arg-type]
    assert classify_claim(42) == "bug_fix"    # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_plan accepts a behavioral expected_behavior-only plan
# ---------------------------------------------------------------------------

def test_validate_plan_accepts_behavioral_expected_behavior_only_plan():
    """A plan with only expected_behavior is valid under validate_plan."""
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {
                "id": "expected_behavior",
                "description": "Run login tests to check credential acceptance and rejection.",
            }
        ],
    }
    assert validate_plan(plan) is True


def test_validate_bug_fix_plan_rejects_expected_behavior_only():
    """validate_bug_fix_plan must still reject plans missing deployment checks."""
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {
                "id": "expected_behavior",
                "description": "Run login tests.",
            }
        ],
    }
    with pytest.raises(ValueError, match="deployment_status"):
        validate_bug_fix_plan(plan)


# ---------------------------------------------------------------------------
# Conservative classification regression tests
# ---------------------------------------------------------------------------

def test_canonical_claim_combined_with_deployment_succeeded_is_bug_fix():
    claim = "The login function accepts valid credentials and rejects invalid credentials, and deployment succeeded"
    assert classify_claim(claim) == "bug_fix"


def test_canonical_claim_combined_with_bug_is_fixed_is_bug_fix():
    claim = "The login function accepts valid credentials and rejects invalid credentials, and the bug is fixed"
    assert classify_claim(claim) == "bug_fix"


def test_canonical_claim_combined_with_production_status_is_bug_fix():
    claim = "The login function accepts valid credentials and rejects invalid credentials in production"
    assert classify_claim(claim) == "bug_fix"


def test_canonical_claim_combined_with_release_is_bug_fix():
    claim = "The login function accepts valid credentials and rejects invalid credentials, and release v1.0 was published"
    assert classify_claim(claim) == "bug_fix"


def test_canonical_claim_multi_sentence_is_bug_fix():
    claim = "The login function accepts valid credentials. The deployment was verified."
    assert classify_claim(claim) == "bug_fix"


def test_canonical_claim_secondary_clause_is_bug_fix():
    claim = "The login function accepts valid credentials and rejects invalid credentials, also verified server health"
    assert classify_claim(claim) == "bug_fix"


# ---------------------------------------------------------------------------
# Mismatched claim validation tests
# ---------------------------------------------------------------------------

def test_validate_plan_with_matching_expected_claim():
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [{"id": "expected_behavior", "description": "Run login tests."}],
    }
    assert validate_plan(plan, expected_claim="The login function accepts valid credentials and rejects invalid credentials.") is True


def test_validate_plan_with_mismatched_expected_claim_raises():
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [{"id": "expected_behavior", "description": "Run login tests."}],
    }
    with pytest.raises(ValueError, match="does not match expected claim"):
        validate_plan(plan, expected_claim="I fixed the login bug and deployed the fix.")


# ---------------------------------------------------------------------------
# validate_behavioral_plan tests
# ---------------------------------------------------------------------------

def test_validate_behavioral_plan_valid():
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [{"id": "expected_behavior", "description": "Run login tests."}],
    }
    assert validate_behavioral_plan(plan, expected_claim="The login function accepts valid credentials and rejects invalid credentials.") is True


def test_validate_behavioral_plan_missing_expected_behavior_raises():
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [{"id": "deployment_status", "description": "Check deployment."}],
    }
    with pytest.raises(ValueError, match="missing required check: expected_behavior"):
        validate_behavioral_plan(plan)


def test_validate_behavioral_plan_preserves_unsupported_checks():
    """A behavioral plan can include extra checks (like deployment_status),
    which are preserved so they will block VERIFIED during evidence collection."""
    plan = {
        "claim": "The login function accepts valid credentials and rejects invalid credentials.",
        "checks": [
            {"id": "expected_behavior", "description": "Run login tests."},
            {"id": "deployment_status", "description": "Check deployment."},
        ],
    }
    assert validate_behavioral_plan(plan) is True


def test_invalid_passwords_claim_is_classified_as_behavioral():
    claim = "The login function accepts invalid passwords."
    assert classify_claim(claim) == "behavioral"


def test_invalid_passwords_claim_with_deployment_is_bug_fix():
    claim = "The login function accepts invalid passwords, and deployment succeeded"
    assert classify_claim(claim) == "bug_fix"


def test_invalid_credentials_claim_is_classified_as_behavioral():
    claim = "The login function accepts invalid credentials."
    assert classify_claim(claim) == "behavioral"


def test_valid_passwords_claim_is_classified_as_behavioral():
    claim = "The login function accepts valid passwords."
    assert classify_claim(claim) == "behavioral"


def test_validate_behavioral_plan_for_invalid_passwords_claim():
    plan = {
        "claim": "The login function accepts invalid passwords.",
        "checks": [{"id": "expected_behavior", "description": "Test invalid passwords."}],
    }
    assert validate_behavioral_plan(plan, expected_claim="The login function accepts invalid passwords.") is True



