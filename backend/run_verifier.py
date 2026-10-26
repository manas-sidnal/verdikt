from pprint import pprint

from backend.planner import create_verification_plan
from backend.evidence_collector import run_login_test
from backend.verdict_engine import evaluate_verdict


def verify_login_fix(claim, deployment_succeeded=None):
    # Step 1: Ask Nemotron what should be checked.
    plan = create_verification_plan(claim)

    # Step 2: Run our supported local behavior check.
    evidence = run_login_test()

    # Step 3: Evaluate the collected evidence.
    verdict = evaluate_verdict(
        deployment_succeeded,
        evidence["passed"],
    )

    return {
        "claim": claim,
        "plan": plan,
        "evidence": evidence,
        "verdict": verdict,
    }


if __name__ == "__main__":
    claim = "I fixed the login bug and deployed the fix."

    result = verify_login_fix(claim)
    pprint(result)
