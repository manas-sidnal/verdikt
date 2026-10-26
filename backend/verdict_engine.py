def evaluate_verdict(deployment_succeeded, login_test_passed):
    """Evaluate a claim using available evidence."""

    # A failed login test contradicts the claim,
    # even if deployment evidence is missing.
    if login_test_passed is False:
        return "CONTRADICTED"

    # A failed deployment also contradicts the claim.
    if deployment_succeeded is False:
        return "CONTRADICTED"

    # We cannot verify success while evidence is missing.
    if deployment_succeeded is None or login_test_passed is None:
        return "INSUFFICIENT EVIDENCE"

    return "VERIFIED"