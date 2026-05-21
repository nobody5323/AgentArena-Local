from src.todo_app import list_todos


def test_list_todos_returns_all_items():
    todos = [
        {"title": "ship", "status": "completed"},
        {"title": "write tests", "status": "active"},
    ]

    assert list_todos(todos) == todos
