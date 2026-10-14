import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import create_app


def test_data_survives_application_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    with TestClient(create_app(url)) as client:
        user = client.post("/users", json={"name": "Persistent"}).json()
    with TestClient(create_app(url)) as client:
        assert client.get("/users").json() == [user]


def test_database_enforces_constraints(client, trip):
    group_id, users = trip
    engine = client.app.state.engine
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO group_members (group_id, user_id, joined_at) VALUES (:g, 9999, CURRENT_TIMESTAMP)"
            ),
            {"g": group_id},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO group_members (group_id, user_id, joined_at) VALUES (:g, :u, CURRENT_TIMESTAMP)"
            ),
            {"g": group_id, "u": users[0]},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settlements (group_id, from_user_id, to_user_id, amount_minor, created_at) VALUES (:g, :u, :v, -1, CURRENT_TIMESTAMP)"
            ),
            {"g": group_id, "u": users[0], "v": users[1]},
        )


def test_non_sqlite_url_is_explicitly_rejected():
    with pytest.raises(ValueError, match="SQLite"):
        create_app("postgresql://localhost/example")
