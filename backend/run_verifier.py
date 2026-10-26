from pprint import pprint

from backend.planner import create_verification_plan
from backend.evidence_collector import (
    _no_runner,
    collect_plan_evidence,
    run_login_test,
)
from backend.verdict_engine import evaluate_evidence_list


def verify_login_fix(claim):
    """Run the full verification pipeline for a claim.

    Steps:
    1. Ask Nemotron to produce a validated verification plan.
    2. Dispatch each check in the plan to its registered runner (or stub).
    3. Evaluate the complete evidence set with evaluate_evidence_list.

    Returns a dict with keys:
        claim       - the original claim string
        plan        - the LLM-generated plan dict
        evidence    - the primary evidence dict (expected_behavior result, or
                      the first item in all_evidence if that check is absent)
        all_evidence - list of one evidence dict per plan check
        verdict     - VERIFIED | CONTRADICTED | INSUFFICIENT EVIDENCE
    """
    # Step 1: Ask Nemotron what should be checked, validating the plan strictly.
    try:
        plan = create_verification_plan(claim)

        # Validate that the plan's claim corresponds to the original user claim.
        if not isinstance(plan, dict):
            raise ValueError("Plan must be a JSON object")
        plan_claim = plan.get("claim")
        if not isinstance(plan_claim, str) or not plan_claim.strip():
            raise ValueError("Plan must contain a non-empty claim")
        if plan_claim.strip() != claim.strip():
            raise ValueError(
                f"Plan claim '{plan_claim.strip()}' does not match user claim '{claim.strip()}'"
            )
    except Exception as exc:
        # A malformed or incomplete model-generated plan, or a model API failure,
        # must not crash with an unhandled HTTP 500 error.
        # Lack of a valid plan is not evidence against the claim, so it must
        # never be labeled CONTRADICTED. Return an explicit INSUFFICIENT EVIDENCE result.
        fallback_plan = {
            "claim": claim,
            "checks": [],
            "error": str(exc),
        }
        fallback_evidence = _no_runner("plan_validation_failed")
        fallback_evidence["stderr"] = f"Plan generation or validation failed: {exc}"
        return {
            "claim": claim,
            "plan": fallback_plan,
            "evidence": fallback_evidence,
            "all_evidence": [fallback_evidence],
            "verdict": "INSUFFICIENT EVIDENCE",
        }

    # Step 2: Collect evidence for every check in the validated plan.
    all_evidence = collect_plan_evidence(plan)

    # Step 3: Evaluate the complete evidence set.
    verdict = evaluate_evidence_list(all_evidence)

    # Preserve the original `evidence` key for API/UI backward compatibility.
    # Use the expected_behavior result if it exists; fall back to the first item,
    # or a safe stub if all_evidence is empty so UI never receives null evidence.
    primary = next(
        (e for e in all_evidence if e.get("check_id") == "expected_behavior"),
        all_evidence[0] if all_evidence else _no_runner("none"),
    )

    return {
        "claim": claim,
        "plan": plan,
        "evidence": primary,
        "all_evidence": all_evidence,
        "verdict": verdict,
    }


if __name__ == "__main__":
    claim = "I fixed the login bug and deployed the fix."

    result = verify_login_fix(claim)
    pprint(result)
