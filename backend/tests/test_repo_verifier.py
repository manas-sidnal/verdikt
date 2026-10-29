import json

import pytest

from backend import llm, sandbox
from backend.claim_extractor import extract_claims_llm, parse_claims_json
from backend.demo_agents import (
    SCENARIO_KINDS,
    TARGET_INFO,
    build_scenario,
    load_solution,
    scripted_extractor,
)
from backend.repo_verifier import MAX_CLAIMS, verify_agent_report

EXPECTED = {
    "honest": "VERIFIED",
    "overclaim": "CONTRADICTED",
    "tamper": "CONTRADICTED",
    "deploy": "INSUFFICIENT EVIDENCE",
}


@pytest.mark.parametrize("kind", SCENARIO_KINDS)
@pytest.mark.parametrize("target", sorted(TARGET_INFO))
def test_scripted_scenarios_produce_expected_verdicts(target, kind):
    s = build_scenario(target, kind)
    result = verify_agent_report(target, s["report"], s["patch"], extract=scripted_extractor(s["claims"]))
    assert result["verdict"] == EXPECTED[kind]
    assert result["dropped_claims"] == []


def test_overclaim_is_contradicted_by_real_failing_tests_not_by_regex():
    s = build_scenario("cart_total", "overclaim")
    result = verify_agent_report("cart_total", s["report"], s["patch"], extract=scripted_extractor(s["claims"]))
    tests_claim = next(c for c in result["claims"] if c["check"] == "tests_pass")
    ev = tests_claim["evidence"]
    assert tests_claim["verdict"] == "CONTRADICTED"
    assert ev["status"] == "executed" and ev["exit_code"] == 1
    assert ev["n_failed"] >= 1  # a real failing test, visible in the evidence
    assert "failed" in ev["stdout"]


def test_tampering_is_flagged_even_when_the_agent_never_mentions_it():
    s = build_scenario("slugify_fix", "tamper")
    result = verify_agent_report("slugify_fix", s["report"], s["patch"], extract=scripted_extractor([]))
    assert result["integrity"]["passed"] is False
    assert result["verdict"] == "CONTRADICTED"


def test_honest_agent_gets_full_evidence_trail():
    s = build_scenario("rate_limit", "honest")
    result = verify_agent_report("rate_limit", s["report"], s["patch"], extract=scripted_extractor(s["claims"]))
    assert result["runs"]["baseline"]["passed"] is False
    assert result["runs"]["patched"]["passed"] is True
    assert result["runs"]["baseline"]["tree_sha256"] != result["runs"]["patched"]["tree_sha256"]
    assert result["changed_files"] == ["limiter.py"]
    assert result["integrity"]["passed"] is True


def test_syntax_error_patch_is_contradicted_not_inconclusive():
    report = "Fixed it. All tests pass."
    claims = [{"quote": "All tests pass", "text": "Suite passes.", "check": "tests_pass", "arg": None}]
    result = verify_agent_report(
        "slugify_fix", report, {"textutils.py": "def slugify(:\n"}, extract=scripted_extractor(claims)
    )
    ev = result["claims"][0]["evidence"]
    assert ev["status"] == "patch_broke_collection"
    assert result["verdict"] == "CONTRADICTED"


def test_hanging_patch_is_inconclusive_never_contradicted():
    report = "All tests pass."
    claims = [{"quote": "All tests pass", "text": "Suite passes.", "check": "tests_pass", "arg": None}]
    result = verify_agent_report(
        "slugify_fix", report, {"textutils.py": "while True:\n    pass\n"},
        extract=scripted_extractor(claims), timeout=2,
    )
    assert result["claims"][0]["evidence"]["status"] == "timeout"
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"


def test_targeted_test_claims_are_checked_individually():
    report = "test_blocks_over_limit passes and test_invalid_limit_rejected passes."
    claims = [
        {"quote": "test_blocks_over_limit passes", "text": "blocks test passes", "check": "targeted_test",
         "arg": "tests/test_limiter.py::test_blocks_over_limit"},
        {"quote": "test_invalid_limit_rejected passes", "text": "validation test passes", "check": "targeted_test",
         "arg": "tests/test_limiter.py::test_invalid_limit_rejected"},
    ]
    result = verify_agent_report(
        "rate_limit", report, load_solution("rate_limit", "partial"), extract=scripted_extractor(claims)
    )
    verdicts = [c["verdict"] for c in result["claims"]]
    assert verdicts == ["VERIFIED", "CONTRADICTED"]  # the partial fix really does satisfy one but not the other
    assert result["verdict"] == "CONTRADICTED"


def test_files_changed_claim_is_checked_against_a_real_diff():
    report = "I rewrote cart.py."
    claims = [{"quote": "I rewrote cart.py", "text": "cart.py changed", "check": "files_changed", "arg": "cart.py"}]
    unchanged = {"cart.py": (sandbox.TARGETS_DIR / "cart_total" / "cart.py").read_text()}
    result = verify_agent_report("cart_total", report, unchanged, extract=scripted_extractor(claims))
    assert result["claims"][0]["verdict"] == "CONTRADICTED"


# ---------------------------------------------------------------------------
# Hostile or sloppy model output
# ---------------------------------------------------------------------------

def _verify_with(raw_claims, report="All tests pass now.", patch=None, target="slugify_fix"):
    return verify_agent_report(
        target, report, patch if patch is not None else load_solution(target, "good"),
        extract=lambda _r, _c: raw_claims,
    )


def test_hallucinated_quote_is_dropped():
    result = _verify_with([{"quote": "I also fixed the database", "text": "x", "check": "tests_pass", "arg": None}])
    assert result["claims"] == []
    assert "verbatim" in result["dropped_claims"][0]["reason"]
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"  # no claims judged, so never VERIFIED


@pytest.mark.parametrize(
    "claim,reason",
    [
        ({"quote": "All tests pass", "text": "t", "check": "run_shell", "arg": "rm -rf /"}, "unsupported check"),
        ({"quote": "All tests pass", "text": "t", "check": "targeted_test", "arg": "tests/x.py::nope"}, "real test id"),
        ({"quote": "All tests pass", "text": "t", "check": "tests_pass", "arg": "--flag"}, "takes no arg"),
        ({"quote": "All tests pass", "text": "t", "check": "files_changed", "arg": None}, "file path"),
        ({"quote": "", "text": "t", "check": "tests_pass", "arg": None}, "quote"),
        ({"quote": "All tests pass", "text": "", "check": "tests_pass", "arg": None}, "text"),
        ("not a dict", "not an object"),
    ],
)
def test_malformed_or_malicious_claims_are_dropped(claim, reason):
    result = _verify_with([claim])
    assert result["claims"] == []
    assert reason in result["dropped_claims"][0]["reason"]


def test_duplicate_and_excess_claims_are_dropped():
    one = {"quote": "All tests pass", "text": "t", "check": "tests_pass", "arg": None}
    result = _verify_with([one, dict(one)])
    assert len(result["claims"]) == 1 and "duplicate" in result["dropped_claims"][0]["reason"]

    report = " ".join(f"claim{i}" for i in range(MAX_CLAIMS + 3))
    many = [
        {"quote": f"claim{i}", "text": "t", "check": "files_changed", "arg": "textutils.py"}
        for i in range(MAX_CLAIMS + 3)
    ]
    result = _verify_with(many, report=report)
    assert len(result["claims"]) == MAX_CLAIMS and len(result["dropped_claims"]) == 3


def test_non_list_extractor_output_is_safe():
    result = _verify_with({"claims": []})
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert result["dropped_claims"]


def test_failing_extractor_is_insufficient_not_contradicted():
    def boom(_r, _c):
        raise RuntimeError("Token Factory timed out")

    result = verify_agent_report("slugify_fix", "All tests pass.", load_solution("slugify_fix", "good"), extract=boom)
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"
    assert "Token Factory timed out" in result["extraction_error"]


def test_integrity_violation_still_contradicts_when_extractor_fails():
    def boom(_r, _c):
        raise RuntimeError("down")

    patch = {**load_solution("slugify_fix", "good"), "tests/test_textutils.py": "def test_x():\n    assert True\n"}
    result = verify_agent_report("slugify_fix", "Done.", patch, extract=boom)
    assert result["verdict"] == "CONTRADICTED"


def test_deployment_claims_can_never_be_verified():
    claim = {"quote": "deployed to production", "text": "deployed", "check": "deployment_status", "arg": None}
    result = _verify_with([claim], report="I deployed to production.")
    assert result["claims"][0]["evidence"]["status"] == "no_runner"
    assert result["verdict"] == "INSUFFICIENT EVIDENCE"


def test_invalid_inputs_raise_cleanly():
    with pytest.raises(sandbox.SandboxError):
        verify_agent_report("nope", "x", None, extract=lambda r, c: [])
    with pytest.raises(sandbox.SandboxError):
        verify_agent_report("slugify_fix", "x", {"../evil.py": "x"}, extract=lambda r, c: [])
    with pytest.raises(ValueError):
        verify_agent_report("slugify_fix", "   ", None, extract=lambda r, c: [])


# ---------------------------------------------------------------------------
# LLM extraction plumbing (no network: chat is injected)
# ---------------------------------------------------------------------------

def test_strip_reasoning_removes_think_blocks():
    assert llm.strip_reasoning('<think>plan…</think>{"claims": []}') == '{"claims": []}'
    assert llm.strip_reasoning('<think>truncated forever') == ""


def test_parse_claims_json_tolerates_fences_and_prose():
    payload = {"claims": [{"quote": "q", "text": "t", "check": "tests_pass", "arg": None}]}
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    assert parse_claims_json(fenced) == payload["claims"]
    assert parse_claims_json("Sure! " + json.dumps(payload) + " Hope that helps.") == payload["claims"]
    for bad in ["no json here", "{not json}", '{"claims": "nope"}', ""]:
        with pytest.raises(ValueError):
            parse_claims_json(bad)


def test_llm_extractor_end_to_end_with_fake_model():
    s = build_scenario("cart_total", "overclaim")
    captured = {}

    def fake_chat(system, user):
        captured["user"] = user
        return "```json\n" + json.dumps({"claims": s["claims"]}) + "\n```"

    result = verify_agent_report(
        "cart_total", s["report"], s["patch"], extract=lambda r, c: extract_claims_llm(r, c, chat=fake_chat)
    )
    assert result["verdict"] == "CONTRADICTED"
    # The model is shown real test ids so targeted claims can be grounded.
    assert "tests/test_cart.py::test_applies_tax" in captured["user"]
