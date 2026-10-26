"""
API tests for backend/api.py.

The verifier is mocked so no real Nebius API call is needed.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)

MOCK_RESULT = {
    "claim": "The login bug is fixed and the deployment is successful.",
    "plan": {
        "claim": "The login bug is fixed and the deployment is successful.",
        "checks": [
            {"id": "deployment_status", "description": "Check deployment records."},
            {"id": "bug_reproduction", "description": "Check if the original bug still occurs."},
            {"id": "expected_behavior", "description": "Test whether login works correctly."},
        ],
    },
    "evidence": {
        "check_id": "expected_behavior",
        "passed": True,
        "status": "executed",
        "exit_code": 0,
        "tests_ran": True,
        "stdout": "3 passed",
        "stderr": "",
        "evidence_source": "pytest",
    },
    "all_evidence": [
        {"check_id": "deployment_status", "passed": None, "status": "no_runner",
         "exit_code": None, "tests_ran": False, "stdout": "", "stderr": "",
         "evidence_source": "none"},
        {"check_id": "bug_reproduction", "passed": None, "status": "no_runner",
         "exit_code": None, "tests_ran": False, "stdout": "", "stderr": "",
         "evidence_source": "none"},
        {"check_id": "expected_behavior", "passed": True, "status": "executed",
         "exit_code": 0, "tests_ran": True, "stdout": "3 passed", "stderr": "",
         "evidence_source": "pytest"},
    ],
    "verdict": "INSUFFICIENT EVIDENCE",
}



def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "verdikt-api"


def test_verify_success():
    with patch("backend.api.verify_login_fix", return_value=MOCK_RESULT) as mock_verify:
        response = client.post(
            "/verify",
            json={"claim": "The login bug is fixed and the deployment is successful."},
        )
    assert response.status_code == 200
    data = response.json()
    assert "claim" in data
    assert "plan" in data
    assert "evidence" in data
    assert "verdict" in data
    mock_verify.assert_called_once_with(
        "The login bug is fixed and the deployment is successful."
    )


def test_verify_empty_claim_rejected():
    """Empty string must fail Pydantic min_length=5 validation → 422."""
    response = client.post("/verify", json={"claim": ""})
    assert response.status_code == 422


def test_verify_too_short_claim_rejected():
    """Claim shorter than 5 chars → 422."""
    response = client.post("/verify", json={"claim": "Hi"})
    assert response.status_code == 422


def test_verify_claim_too_long_rejected():
    """Claim longer than 2000 chars → 422."""
    response = client.post("/verify", json={"claim": "x" * 2001})
    assert response.status_code == 422


def test_verify_missing_claim_field_rejected():
    """Request body without 'claim' field → 422."""
    response = client.post("/verify", json={})
    assert response.status_code == 422


def test_verify_verifier_failure_returns_500():
    """When the verifier raises, the API must return 500 without leaking internals."""
    with patch("backend.api.verify_login_fix", side_effect=RuntimeError("internal boom")):
        response = client.post(
            "/verify",
            json={"claim": "Valid claim that triggers a server error."},
        )
    assert response.status_code == 500
    data = response.json()
    # Must not expose the internal exception message or traceback.
    assert "boom" not in data.get("detail", "")
    assert "RuntimeError" not in data.get("detail", "")
    assert "internal" not in data.get("detail", "").lower()


def test_verify_invalid_passwords_claim_returns_200_and_contradicted():
    """'The login function accepts invalid passwords.' must return 200 OK and CONTRADICTED, not 500."""
    behavioral_plan = {
        "claim": "The login function accepts invalid passwords.",
        "checks": [{"id": "expected_behavior", "description": "Test invalid passwords."}],
    }
    with patch("backend.run_verifier.create_verification_plan", return_value=behavioral_plan):
        response = client.post(
            "/verify",
            json={"claim": "The login function accepts invalid passwords."},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "CONTRADICTED"
    assert data["evidence"]["passed"] is False


def test_verify_model_plan_missing_checks_returns_200_and_insufficient_evidence():
    """A model plan missing required checks must return 200 OK and INSUFFICIENT EVIDENCE, not 500."""
    with patch(
        "backend.run_verifier.create_verification_plan",
        side_effect=ValueError("Bug-fix plan is missing required checks: deployment_status"),
    ):
        response = client.post(
            "/verify",
            json={"claim": "I fixed the login bug and deployed the fix."},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "INSUFFICIENT EVIDENCE"
    assert data["evidence"]["passed"] is None


def test_verify_model_api_failure_returns_200_and_insufficient_evidence():
    """A model API network or parsing failure must return 200 OK and INSUFFICIENT EVIDENCE, not 500."""
    with patch(
        "backend.run_verifier.create_verification_plan",
        side_effect=RuntimeError("Nebius connection error"),
    ):
        response = client.post(
            "/verify",
            json={"claim": "The login function accepts valid credentials and rejects invalid credentials."},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "INSUFFICIENT EVIDENCE"
    assert data["evidence"]["passed"] is None

