from examples.python_debug_login.repo.src.login_app import login


def test_login_accepts_valid_password_without_storage_whitespace():
    assert login("alice", "secret")


def test_login_rejects_invalid_password():
    assert not login("alice", "wrong")
