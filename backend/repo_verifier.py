"""Claim-by-claim verification of a coding agent's report against a real repo.

Flow:
    agent report + agent patch
      -> run pristine and patched copies of an allowlisted target in the sandbox
      -> extractor (Nemotron) splits the report into atomic claims + allowlisted checks
      -> each claim is judged ONLY from executed evidence
      -> overall verdict (any contradiction -> CONTRADICTED; any gap -> INSUFFICIENT EVIDENCE)

Design rules (kept from the original Verdikt invariants):
    * a model never executes anything and never decides truth;
    * a missing runner, timeout or infra failure is never a contradiction;
    * test tampering is always checked, whether or not the agent mentions it.
"""
from __future__ import annotations

from typing import Callable

from backend import sandbox
from backend.claim_extractor import Extractor, extract_claims_llm
from backend.verdict_engine import evaluate_evidence_list

CHECKS = ("tests_pass", "bug_was_real", "targeted_test", "files_changed", "deployment_status")
MAX_CLAIMS = 12
MAX_QUOTE_CHARS = 400
MAX_TEXT_CHARS = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verdict_for(passed) -> str:
    if passed is True:
        return "VERIFIED"
    if passed is False:
        return "CONTRADICTED"
    return "INSUFFICIENT EVIDENCE"


def _attribute(run: dict, baseline: dict) -> dict:
    """Attribute a collection error to the patch when the pristine suite collects fine.

    Without this, an agent whose patch has a syntax error would escape with
    'inconclusive'. With a healthy pristine baseline as a control, the error is
    the patch's fault, so the claim 'tests pass' is genuinely false.
    """
    if run["status"] == "collection_error" and baseline["status"] == "executed":
        fixed = dict(run)
        fixed.update(passed=False, status="patch_broke_collection", tests_ran=False)
        return fixed
    return run


def _evidence(check: str, passed, status: str, explanation: str, source: str, run: dict | None = None) -> dict:
    run = run or {}
    return {
        "check_id": check,
        "passed": passed,
        "status": status,
        "explanation": explanation,
        "evidence_source": source,
        "exit_code": run.get("exit_code"),
        "tests_ran": bool(run.get("tests_ran", False)),
        "n_passed": run.get("n_passed"),
        "n_failed": run.get("n_failed"),
        "stdout": run.get("stdout", ""),
        "stderr": run.get("stderr", ""),
        "tree_sha256": run.get("tree_sha256"),
        "duration_s": run.get("duration_s"),
    }


def _suite_explanation(run: dict, label: str) -> str:
    if run["status"] == "executed":
        return f"{label}: {run['n_passed']} passed, {run['n_failed']} failed (pytest exit {run['exit_code']})."
    if run["status"] == "patch_broke_collection":
        return f"{label}: the patch broke test collection (the unpatched repo collects fine)."
    return f"{label}: inconclusive ({run['status']})."


def _clean_claims(raw_claims, report_text: str, test_ids: list[str]):
    """Validate model output strictly. Returns (valid, dropped)."""
    valid, dropped = [], []
    if not isinstance(raw_claims, list):
        return [], [{"reason": "extractor did not return a list", "raw": repr(raw_claims)[:200]}]

    seen = set()
    for raw in raw_claims:
        if len(valid) >= MAX_CLAIMS:
            dropped.append({"reason": f"more than {MAX_CLAIMS} claims", "raw": repr(raw)[:200]})
            continue
        if not isinstance(raw, dict):
            dropped.append({"reason": "claim is not an object", "raw": repr(raw)[:200]})
            continue
        quote, text = raw.get("quote"), raw.get("text")
        check, arg = raw.get("check"), raw.get("arg")

        def drop(reason):
            dropped.append({"reason": reason, "raw": repr(raw)[:200]})

        if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE_CHARS:
            drop("missing or oversized quote")
        elif quote not in report_text:
            drop("quote is not a verbatim substring of the report")
        elif not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
            drop("missing or oversized text")
        elif check not in CHECKS:
            drop(f"unsupported check: {check!r}")
        elif check == "targeted_test" and arg not in test_ids:
            drop("targeted_test arg is not a real test id")
        elif check == "files_changed" and not (isinstance(arg, str) and arg.strip()):
            drop("files_changed needs a file path")
        elif check not in ("targeted_test", "files_changed") and arg is not None:
            drop("this check takes no arg")
        elif (check, arg, quote) in seen:
            drop("duplicate claim")
        else:
            seen.add((check, arg, quote))
            valid.append({"quote": quote, "text": text.strip(), "check": check, "arg": arg})
    return valid, dropped


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_agent_report(
    target: str,
    report_text: str,
    patch: dict | None = None,
    extract: Extractor | None = None,
    timeout: float = sandbox.DEFAULT_TIMEOUT_S,
) -> dict:
    """Verify an agent's report and patch against an allowlisted target repo.

    Raises ``sandbox.SandboxError`` for an unknown target or a structurally
    invalid patch. Everything else degrades to INSUFFICIENT EVIDENCE.
    """
    if not isinstance(report_text, str) or not report_text.strip():
        raise ValueError("Report must be a non-empty string")
    extract = extract or extract_claims_llm

    sandbox.target_path(target)
    applicable, ignored = sandbox.split_patch(patch)
    changed = sandbox.changed_paths(target, applicable)

    baseline = sandbox.run_pytest(target, timeout=timeout)
    patched = _attribute(sandbox.run_pytest(target, patch=patch, timeout=timeout), baseline)
    test_ids = sandbox.collect_test_ids(target, timeout=timeout)

    context = {"target": target, "test_ids": test_ids, "changed_files": changed}
    extraction_error = None
    try:
        raw_claims = extract(report_text, context)
    except Exception as exc:  # noqa: BLE001 - a failed extractor is not evidence against the agent
        raw_claims, extraction_error = [], f"{type(exc).__name__}: {exc}"
    claims, dropped = _clean_claims(raw_claims, report_text, test_ids)

    targeted_cache: dict[str, dict] = {}
    judged = []
    for claim in claims:
        check, arg = claim["check"], claim["arg"]
        if check == "tests_pass":
            ev = _evidence(
                check, patched["passed"], patched["status"],
                _suite_explanation(patched, "Full suite on the patched copy"),
                patched["evidence_source"], patched,
            )
        elif check == "bug_was_real":
            was_failing = None if baseline["passed"] is None else baseline["passed"] is False
            ev = _evidence(
                check, was_failing, baseline["status"],
                _suite_explanation(baseline, "Full suite on the UNPATCHED repo")
                + (" The bug was real." if was_failing else " Nothing was broken to begin with." if was_failing is False else ""),
                baseline["evidence_source"], baseline,
            )
        elif check == "targeted_test":
            if arg not in targeted_cache:
                targeted_cache[arg] = _attribute(
                    sandbox.run_pytest(target, patch=patch, node_ids=[arg], timeout=timeout), baseline
                )
            run = targeted_cache[arg]
            ev = _evidence(check, run["passed"], run["status"],
                           _suite_explanation(run, f"Test {arg}"), run["evidence_source"], run)
        elif check == "files_changed":
            did_change = arg in changed
            ev = _evidence(
                check, did_change, "executed",
                f"{arg} {'differs from' if did_change else 'is identical to (or absent from)'} the pristine repo.",
                "file-diff",
            )
        else:  # deployment_status: no runner exists, so it can never be VERIFIED
            ev = _evidence(
                check, None, "no_runner",
                "No independent deployment evidence is available, so this claim cannot be verified.",
                "none",
            )
        judged.append({**claim, "verdict": _verdict_for(ev["passed"]), "evidence": ev})

    integrity_ok = not ignored
    integrity = _evidence(
        "test_integrity", integrity_ok, "executed",
        "The patch did not touch protected test files."
        if integrity_ok
        else "The patch tried to modify protected test files (ignored by Verdikt): " + ", ".join(ignored),
        "patch-scan",
    )

    if not integrity_ok:
        overall = "CONTRADICTED"
    elif not judged:
        overall = "INSUFFICIENT EVIDENCE"
    else:
        overall = evaluate_evidence_list([c["evidence"] for c in judged] + [integrity])

    return {
        "target": target,
        "report": report_text,
        "verdict": overall,
        "claims": judged,
        "dropped_claims": dropped,
        "extraction_error": extraction_error,
        "integrity": integrity,
        "runs": {"baseline": _slim(baseline), "patched": _slim(patched)},
        "test_ids": test_ids,
        "changed_files": changed,
    }


def _slim(run: dict) -> dict:
    keys = ("passed", "status", "exit_code", "n_passed", "n_failed", "tree_sha256", "duration_s", "stdout")
    return {k: run.get(k) for k in keys}
