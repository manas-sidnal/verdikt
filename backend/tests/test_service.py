import json

import pytest

from backend import sandbox, service
from backend.demo_agents import SCENARIO_KINDS, TARGET_INFO

EXPECTED = {
    "honest": "VERIFIED",
    "overclaim": "CONTRADICTED",
    "tamper": "CONTRADICTED",
    "deploy": "INSUFFICIENT EVIDENCE",
}


@pytest.fixture(autouse=True)
def _fresh_limits():
    service.reset_limits_for_tests()
    yield
    service.reset_limits_for_tests()


@pytest.fixture
def live_on(monkeypatch):
    monkeypatch.setattr(service, "live_available", lambda: True)
    monkeypatch.setattr(service, "live_model", lambda: "fake/nemotron")


def test_describe_lists_every_target_and_scenario(monkeypatch):
    monkeypatch.setattr(service, "live_available", lambda: False)
    d = service.describe()
    assert {t["name"] for t in d["targets"]} == set(TARGET_INFO)
    for t in d["targets"]:
        assert [s["kind"] for s in t["scenarios"]] == list(SCENARIO_KINDS)
        assert all(s["report"].strip() for s in t["scenarios"])
    assert d["live_available"] is False and d["live_model"] is None
    json.dumps(d)  # must be JSON-serialisable


@pytest.mark.parametrize("scenario", SCENARIO_KINDS)
def test_replay_run_returns_expected_verdict_and_metadata(scenario):
    r = service.run_demo("slugify_fix", scenario)
    assert r["verdict"] == EXPECTED[scenario]
    assert r["mode"] == "replay" and r["model"] is None
    assert r["scenario"] == scenario and r["scenario_label"]
    assert r["patch_files"] and r["elapsed_s"] >= 0
    json.dumps(r)


def test_replay_ignores_custom_report_text():
    r = service.run_demo("cart_total", "overclaim", "replay", report="I fixed everything, trust me")
    assert r["report"] != "I fixed everything, trust me"
    assert r["verdict"] == "CONTRADICTED"


@pytest.mark.parametrize(
    "args",
    [
        ("nope", "honest", "replay"),
        ("cart_total", "nope", "replay"),
        ("cart_total", "honest", "nope"),
        ("../etc", "honest", "replay"),
    ],
)
def test_bad_inputs_raise_validation_errors(args):
    with pytest.raises((sandbox.SandboxError, ValueError)):
        service.run_demo(*args)


def test_oversized_report_rejected(live_on):
    with pytest.raises(ValueError):
        service.run_demo("cart_total", "honest", "live", report="x" * (service.MAX_REPORT_CHARS + 1))


def test_live_requires_credentials(monkeypatch):
    monkeypatch.setattr(service, "live_available", lambda: False)
    with pytest.raises(service.LiveUnavailable):
        service.run_demo("cart_total", "honest", "live")


def test_live_uses_the_extractor_and_custom_report(live_on, monkeypatch):
    seen = {}

    def fake_extract(report_text, context):
        seen["report"] = report_text
        seen["tests"] = context["test_ids"]
        return [{"quote": "All good", "text": "Suite passes.", "check": "tests_pass", "arg": None}]

    monkeypatch.setattr(service, "extract_claims_llm", fake_extract)
    r = service.run_demo("cart_total", "overclaim", "live", report="  Done. All good, shipped.  ")
    assert seen["report"] == "Done. All good, shipped."
    assert "tests/test_cart.py::test_applies_tax" in seen["tests"]
    assert r["mode"] == "live" and r["model"] == "fake/nemotron"
    assert r["verdict"] == "CONTRADICTED"  # the stored patch is a half-fix, whatever the report says
    assert r["claims"][0]["evidence"]["status"] == "executed"


def test_live_falls_back_to_default_report_when_blank(live_on, monkeypatch):
    seen = {}
    monkeypatch.setattr(service, "extract_claims_llm", lambda text, ctx: seen.setdefault("r", text) and [])
    service.run_demo("cart_total", "honest", "live", report="   ")
    assert "Fixed" in seen["r"]


def test_live_extractor_failure_is_insufficient_not_a_crash(live_on, monkeypatch):
    def boom(_t, _c):
        raise RuntimeError("Token Factory 429")

    monkeypatch.setattr(service, "extract_claims_llm", boom)
    r = service.run_demo("cart_total", "honest", "live")
    assert r["verdict"] == "INSUFFICIENT EVIDENCE"
    assert "Token Factory 429" in r["extraction_error"]


def test_live_runs_are_rate_limited_but_replay_is_not(live_on, monkeypatch):
    service.reset_limits_for_tests(live_limit=1)
    monkeypatch.setattr(service, "extract_claims_llm", lambda t, c: [])
    service.run_demo("cart_total", "honest", "live")
    with pytest.raises(service.RateLimited):
        service.run_demo("cart_total", "honest", "live")
    assert service.run_demo("cart_total", "honest", "replay")["verdict"] == "VERIFIED"


def test_busy_when_no_run_slots_free(monkeypatch):
    service.reset_limits_for_tests(slots=1)
    monkeypatch.setattr(service, "_ACQUIRE_TIMEOUT_S", 0.05)
    assert service._run_slots.acquire(timeout=1)
    try:
        with pytest.raises(service.Busy):
            service.run_demo("cart_total", "honest", "replay")
    finally:
        service._run_slots.release()
    assert service.run_demo("cart_total", "honest", "replay")["verdict"] == "VERIFIED"


def test_slot_is_released_after_a_failed_run(live_on, monkeypatch):
    service.reset_limits_for_tests(slots=1)
    monkeypatch.setattr(service, "_ACQUIRE_TIMEOUT_S", 0.05)

    def explode(*_a, **_k):
        raise RuntimeError("sandbox exploded")

    monkeypatch.setattr(service, "verify_agent_report", explode)
    with pytest.raises(RuntimeError):
        service.run_demo("cart_total", "honest", "replay")
    monkeypatch.undo()
    assert service.run_demo("cart_total", "honest", "replay")["verdict"] == "VERIFIED"


def test_sliding_window_limiter_expires_old_hits():
    now = [0.0]
    limiter = service.SlidingWindowLimiter(2, 10, clock=lambda: now[0])
    assert limiter.allow() and limiter.allow()
    assert limiter.allow() is False
    now[0] = 10.0
    assert limiter.allow() is True
