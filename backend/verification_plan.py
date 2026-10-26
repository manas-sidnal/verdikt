ALLOWED_CHECKS = {
    "deployment_status",
    "bug_reproduction",
    "expected_behavior",
}


def validate_plan(plan):
    """Validate a verification plan before it can be used."""

    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object")

    claim = plan.get("claim")
    checks = plan.get("checks")

    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("Plan must contain a non-empty claim")

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


def validate_bug_fix_plan(plan):
    """Ensure a bug-fix plan covers deployment and current behavior."""

    validate_plan(plan)

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