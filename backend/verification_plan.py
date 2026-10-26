import re

ALLOWED_CHECKS = {
    "deployment_status",
    "bug_reproduction",
    "expected_behavior",
}

# ---------------------------------------------------------------------------
# Claim classifier
# ---------------------------------------------------------------------------

# Positive matching: A claim must match at least one of these phrase sets
# to be a candidate for behavioral verification.
# (All phrases in the chosen tuple must be present in the lower-cased claim.)
_BEHAVIORAL_PHRASE_SETS: tuple[tuple[str, ...], ...] = (
    # "The login function accepts valid credentials and rejects invalid credentials."
    ("login", "valid credential", "invalid credential"),
    # Shorter variant: "login function accepts valid credentials"
    ("login function", "accept", "valid credential"),
    # "login accepts valid credentials and rejects invalid"
    ("login", "accept", "reject", "credential"),
    # Claims asserting behavior on invalid passwords, e.g. "The login function accepts invalid passwords"
    ("login", "invalid password"),
    # Claims asserting behavior on valid passwords, e.g. "The login function accepts valid passwords"
    ("login", "valid password"),
    # Claims asserting behavior on invalid credentials, e.g. "The login function accepts invalid credentials"
    ("login", "invalid credential"),
)

# Negative / disqualifying indicators: If ANY of these patterns match,
# the claim asserts something beyond purely local login credential verification
# (such as deployment, bug fixes, releases, production status, infrastructure,
# other features, or external system state). Such claims MUST NOT qualify
# for behavioral-only verification and are classified as "bug_fix".
_DISQUALIFYING_PATTERNS = re.compile(
    r"\b("
    # Deployment / infrastructure / environment / servers
    r"deploy|deployment|deployments|deployed|deploying|"
    r"production|prod|staging|stage|server|servers|infra|infrastructure|"
    r"cloud|ci|cd|pipeline|pipelines|cluster|k8s|kubernetes|docker|container|containers|"
    # Bug fix / lifecycle / defect resolution
    r"bug|bugs|fix|fixed|fixes|fixing|defect|defects|issue|issues|"
    r"patch|patched|patches|patching|resolve|resolved|resolves|resolving|"
    r"reproduce|reproduced|reproducing|reproduction|regression|regressions|"
    # Release / shipping / rollout
    r"release|released|releases|releasing|ship|shipped|shipping|"
    r"rollout|publish|published|live|"
    # Source control / repository / PR
    r"commit|commits|committed|committing|merge|merged|merging|"
    r"pr|prs|pull\s+request|pull\s+requests|branch|branches|"
    # Unrelated features / external systems / side-effects
    r"database|databases|db|migration|migrations|migrated|"
    r"logout|signout|sign-out|signup|sign-up|register|registration|"
    r"reset|oauth|sso|token|tokens|session|sessions|cookie|cookies|"
    r"email|sms|2fa|mfa|otp|"
    r"ui|frontend|backend|endpoint|api|service|services|"
    r"performance|latency|scale|scaling|speed|"
    r"test\s+suite|all\s+tests|unit\s+tests|e2e|integration|"
    r"audit|audited|notification|notifications|notify|"
    r"dashboard|analytics|settings|profile|profiles|account|accounts"
    r")\b",
    re.IGNORECASE,
)

# Connectors and conjunctions that introduce secondary clauses or assertions
_SECONDARY_CLAUSE_PATTERN = re.compile(
    r"(,\s*(and|also|plus|with|as\s+well\s+as)\b|\b(also|plus|as\s+well\s+as|furthermore|moreover|in\s+addition|besides)\b)",
    re.IGNORECASE,
)


def classify_claim(claim: str) -> str:
    """Classify a claim as 'behavioral' or 'bug_fix'.

    Returns
    -------
    'behavioral'
        The claim is strictly and solely about observable login credential
        acceptance/rejection. A plan containing 'expected_behavior' is required.
    'bug_fix'
        The claim mentions fixing a bug, deploying a change, production status,
        releases, or contains broader/ambiguous scope. All three checks
        (deployment_status, bug_reproduction, expected_behavior) are required.

    Safety invariants
    -----------------
    1. Conservative by default: Any claim not unequivocally restricted to
       login credential verification defaults to 'bug_fix'.
    2. Negative matching: Any claim containing any assertion about deployment,
       bug fixes, production environments, or external systems is rejected
       from the 'behavioral' category.
    3. Ambiguity rejection: Multi-sentence claims, claims with compound
       secondary clauses, or multiple conjunctions default to 'bug_fix'.
    4. Code-controlled: Operates only on static allowlists and regex patterns.
       Never executes, evaluates, or shells out user input.
    """
    if not isinstance(claim, str) or not claim.strip():
        return "bug_fix"

    lower = claim.lower().strip()

    # Disqualify if any broader claim or infrastructure indicators are present
    if _DISQUALIFYING_PATTERNS.search(lower):
        return "bug_fix"

    # Disqualify multi-sentence or multi-statement claims (separated by ; or period followed by space)
    sentences = [s.strip() for s in re.split(r"[;\n]|\.\s+", lower.rstrip(".")) if s.strip()]
    if len(sentences) > 1:
        return "bug_fix"

    # Disqualify secondary/appended clauses or supplemental connectors
    if _SECONDARY_CLAUSE_PATTERN.search(lower):
        return "bug_fix"

    # Disqualify compound claims with multiple 'and's (e.g., "accepts X and rejects Y and Z")
    if len(re.findall(r"\band\b", lower)) > 1:
        return "bug_fix"

    # Must match at least one approved positive behavioral phrase set
    for phrase_set in _BEHAVIORAL_PHRASE_SETS:
        if all(phrase in lower for phrase in phrase_set):
            return "behavioral"

    return "bug_fix"


def validate_plan(plan, expected_claim=None):
    """Validate a verification plan before it can be used.

    Args:
        plan: The plan dict to validate.
        expected_claim: Optional expected claim string (e.g. the original user claim).
                        If provided, plan['claim'] must match expected_claim.

    Raises:
        ValueError: If plan is not a dict, missing required fields, has unsupported
                    check IDs, or plan['claim'] does not match expected_claim.
    """
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object")

    claim = plan.get("claim")
    checks = plan.get("checks")

    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("Plan must contain a non-empty claim")

    if expected_claim is not None:
        if not isinstance(expected_claim, str) or not expected_claim.strip():
            raise ValueError("Expected claim must be a non-empty string")
        if claim.strip() != expected_claim.strip():
            raise ValueError(
                f"Plan claim '{claim.strip()}' does not match expected claim '{expected_claim.strip()}'"
            )

    if not isinstance(checks, list) or not checks:
        raise ValueError("Plan must contain at least one check")

    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("Each check must be an object")

        check_id = check.get("id")
        description = check.get("description")

        if check_id not in ALLOWED_CHECKS:
            raise ValueError(f"Unsupported check: {check_id}")

        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"Check '{check_id}' needs a description"
            )

    return True


def validate_behavioral_plan(plan, expected_claim=None):
    """Validate a plan for a behavioral claim.

    Requires an 'expected_behavior' check. Unsupported additional checks
    (such as deployment_status or bug_reproduction) are allowed to remain
    in the plan so that they will be collected as unsupported/no_runner stubs
    and block VERIFIED, but the plan must contain at least 'expected_behavior'.
    """
    validate_plan(plan, expected_claim=expected_claim)

    check_ids = {check["id"] for check in plan["checks"]}
    if "expected_behavior" not in check_ids:
        raise ValueError(
            "Behavioral plan is missing required check: expected_behavior"
        )

    return True


def validate_bug_fix_plan(plan, expected_claim=None):
    """Ensure a bug-fix plan covers deployment and current behavior."""
    validate_plan(plan, expected_claim=expected_claim)

    check_ids = {check["id"] for check in plan["checks"]}

    required_checks = {
        "deployment_status",
        "bug_reproduction",
        "expected_behavior",
    }

    missing_checks = required_checks - check_ids

    if missing_checks:
        raise ValueError(
            f"Bug-fix plan is missing required checks: "
            f"{', '.join(sorted(missing_checks))}"
        )

    return True