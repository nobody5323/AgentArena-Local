from examples.python_debug_login.repo.src.login_app import login


def test_login_rejects_unknown_user():
    assert not login("missing", "secret")


def test_login_rejects_invalid_password():
    assert not login("alice", "wrong")

