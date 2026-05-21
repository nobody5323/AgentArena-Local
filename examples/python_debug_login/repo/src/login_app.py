USERS = {
    "alice": " secret ",
}


def login(username, password):
    stored = USERS.get(username)
    if stored is None:
        return False
    return stored == password
