from login_app import login


def test_valid_login_succeeds():
    assert login("demo", "correct-password") is True


def test_invalid_password_is_rejected():
    assert login("demo", "wrong-password") is False


def test_unknown_user_is_rejected():
    assert login("unknown", "correct-password") is False
