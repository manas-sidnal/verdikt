"""HTTP tests for the /demo endpoints (real sandbox runs in replay mode; no network)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend import sandbox, service
from backend.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_limits():
    service.reset_limits_for_tests()
    yield
    service.reset_limits_for_tests()


def test_demo_config_lists_targets_and_scenarios():
    r = client.get("/demo/config")
    assert r.status_code == 200
    body = r.json()
    names = {t["name"] for t in body["targets"]}
    assert {"slugify_fix", "cart_total", "rate_limit"} <= names
    assert [s["kind"] for s in body["targets"][0]["scenarios"]] == ["honest", "overclaim", "tamper", "deploy"]
    assert isinstance(body["live_available"], bool)


@pytest.mark.parametrize(
    "scenario,verdict",
    [("honest", "VERIFIED"), ("overclaim", "CONTRADICTED"), ("tamper", "CONTRADICTED"), ("deploy", "INSUFFICIENT EVIDENCE")],
)
def test_replay_verify_returns_real_verdicts(scenario, verdict):
    r = client.post("/demo/verify", json={"target": "cart_total", "scenario": scenario})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == verdict
    assert body["mode"] == "replay"
    assert body["runs"]["baseline"]["passed"] is False


def test_response_shape_has_what_the_ui_needs():
    body = client.post("/demo/verify", json={"target": "rate_limit", "scenario": "overclaim"}).json()
    for key in ("claims", "integrity", "runs", "report", "scenario_label", "patch_files", "dropped_claims"):
        assert key in body
    claim = body["claims"][0]
    assert {"quote", "text", "check", "verdict", "evidence"} <= set(claim)
    assert {"explanation", "status", "passed", "evidence_source"} <= set(claim["evidence"])


@pytest.mark.parametrize(
    "payload",
    [
        {"target": "cart_total", "scenario": "nope"},
        {"target": "cart_total", "scenario": "honest", "mode": "nope"},
        {"scenario": "honest"},
        {"target": "", "scenario": "honest"},
        {"target": "cart_total", "scenario": "honest", "report": "x" * 5000},
    ],
)
def test_invalid_requests_are_422(payload):
    assert client.post("/demo/verify", json=payload).status_code == 422


def test_unknown_target_is_422_not_500():
    r = client.post("/demo/verify", json={"target": "../../etc", "scenario": "honest"})
    assert r.status_code == 422


def test_client_cannot_supply_a_patch():
    # Extra fields are ignored; the server only ever runs its own stored scenarios.
    r = client.post(
        "/demo/verify",
        json={"target": "cart_total", "scenario": "honest", "patch": {"cart.py": "import os; os.system('id')"}},
    )
    assert r.status_code == 200
    assert "cart.py" in r.json()["patch_files"]
    assert r.json()["verdict"] == "VERIFIED"


def test_live_without_credentials_is_503():
    with patch.object(service, "live_available", return_value=False):
        r = client.post("/demo/verify", json={"target": "cart_total", "scenario": "honest", "mode": "live"})
    assert r.status_code == 503


@pytest.mark.parametrize(
    "exc,code",
    [
        (service.RateLimited("slow down"), 429),
        (service.Busy("busy"), 503),
        (service.LiveUnavailable("no key"), 503),
        (sandbox.SandboxError("bad"), 422),
        (RuntimeError("secret internal detail"), 500),
    ],
)
def test_errors_map_to_status_codes_without_leaking_details(exc, code):
    with patch("backend.api.service.run_demo", side_effect=exc):
        r = client.post("/demo/verify", json={"target": "cart_total", "scenario": "honest"})
    assert r.status_code == code
    if code == 500:
        assert "secret internal detail" not in r.text


def test_legacy_verify_endpoint_still_exists():
    assert client.get("/health").json()["status"] == "ok"
