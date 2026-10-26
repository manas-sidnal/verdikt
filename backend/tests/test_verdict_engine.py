from verdict_engine import evaluate_verdict


def test_all_evidence_supports_claim():
    assert evaluate_verdict(True, True) == "VERIFIED"


def test_failed_login_test_contradicts_claim():
    assert evaluate_verdict(True, False) == "CONTRADICTED"


def test_failed_deployment_contradicts_claim():
    assert evaluate_verdict(False, True) == "CONTRADICTED"


def test_missing_deployment_evidence():
    assert (
        evaluate_verdict(None, True)
        == "INSUFFICIENT EVIDENCE"
    )


def test_missing_login_test_evidence():
    assert (
        evaluate_verdict(True, None)
        == "INSUFFICIENT EVIDENCE"
    )
