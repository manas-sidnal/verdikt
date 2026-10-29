def evaluate_verdict(deployment_succeeded, login_test_passed):
    """Evaluate a claim using available evidence.

    Original two-argument form retained for backward compatibility with
    existing tests and scripts.
    """

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


def evaluate_evidence_list(evidence_list: list) -> str:
    """Evaluate a verdict from a list of evidence dicts.

    Verdict rules (applied in order):
    1. If any evidence has ``passed is False`` (genuine contradiction),
       the claim is CONTRADICTED.
    2. If no genuine contradiction exists but required evidence is missing
       or inconclusive (``passed is None``, unsupported check, timeout,
       runner exception, collection error), or the list is empty, return
       INSUFFICIENT EVIDENCE.
    3. Return VERIFIED only when every required check has trustworthy
       passing evidence (``passed is True``).

    An unexecuted, inconclusive, or unsupported check is never treated as passing.

    Args:
        evidence_list: A list of dicts as returned by collect_plan_evidence().
                       Each dict must contain a ``passed`` key whose value is
                       True, False, or None.

    Returns:
        "CONTRADICTED", "INSUFFICIENT EVIDENCE", or "VERIFIED".
    """
    if not evidence_list:
        return "INSUFFICIENT EVIDENCE"

    for item in evidence_list:
        if isinstance(item, dict) and item.get("passed") is False:
            return "CONTRADICTED"

    for item in evidence_list:
        if not isinstance(item, dict) or item.get("passed") is not True:
            return "INSUFFICIENT EVIDENCE"

    return "VERIFIED"