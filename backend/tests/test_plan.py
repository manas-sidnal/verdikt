import pytest

from verification_plan import validate_plan, validate_bug_fix_plan


def test_valid_plan():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check whether deployment succeeded.",
            },
            {
                "id": "bug_reproduction",
                "description": "Test whether the login bug still occurs.",
            },
        ],
    }

    assert validate_plan(plan) is True


def test_missing_claim():
    plan = {
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment.",
            }
        ]
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_empty_checks():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_unsupported_check():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [
            {
                "id": "delete_database",
                "description": "Delete the database.",
            }
        ],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)


def test_missing_description():
    plan = {
        "claim": "The bug is fixed.",
        "checks": [
            {"id": "deployment_status"}
        ],
    }

    with pytest.raises(ValueError):
        validate_plan(plan)



def test_complete_bug_fix_plan():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment records.",
            },
            {
                "id": "bug_reproduction",
                "description": "Check whether the original bug existed.",
            },
            {
                "id": "expected_behavior",
                "description": "Test whether login works now.",
            },
        ],
    }

    assert validate_bug_fix_plan(plan) is True


def test_bug_fix_plan_missing_current_behavior_check():
    plan = {
        "claim": "I fixed the login bug and deployed the fix.",
        "checks": [
            {
                "id": "deployment_status",
                "description": "Check deployment records.",
            },
            {
                "id": "bug_reproduction",
                "description": "Check whether the original bug existed.",
            },
        ],
    }

    with pytest.raises(ValueError, match="expected_behavior"):
        validate_bug_fix_plan(plan)
