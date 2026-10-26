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
        "exit_code": 0,
        "tests_ran": True,
        "stdout": "3 passed",
        "stderr": "",
        "evidence_source": "pytest",
    },
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
