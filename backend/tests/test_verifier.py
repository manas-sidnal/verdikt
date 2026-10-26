def verify_deployment(deployment_succeeded, bug_reproduced):
    # Missing evidence must never count as success.
    if deployment_succeeded is None or bug_reproduced is None:
        return "INSUFFICIENT EVIDENCE"

    # Either failed deployment or reproducible bug contradicts
    # the claim that deployment succeeded and the bug was fixed.
    if not deployment_succeeded or bug_reproduced:
        return "CONTRADICTED"

    return "VERIFIED"


def test_deployment_succeeded_but_bug_remains():
    assert verify_deployment(True, True) == "CONTRADICTED"


def test_deployment_failed():
    assert verify_deployment(False, False) == "CONTRADICTED"


def test_deployment_and_fix_succeeded():
    assert verify_deployment(True, False) == "VERIFIED"


def test_missing_deployment_evidence():
    assert verify_deployment(None, False) == "INSUFFICIENT EVIDENCE"


def test_missing_bug_test_evidence():
    assert verify_deployment(True, None) == "INSUFFICIENT EVIDENCE"
