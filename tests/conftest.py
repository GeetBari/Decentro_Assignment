import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def trip(client):
    users = [
        client.post("/users", json={"name": name}).json() for name in ["Mohit", "Rahul", "Ankit"]
    ]
    group = client.post("/groups", json={"name": "Goa Trip"}).json()
    for user in users:
        response = client.post(f"/groups/{group['id']}/members", json={"user_id": user["id"]})
        assert response.status_code == 201
    return group["id"], [user["id"] for user in users]


def add_expense(client, trip, amount="1200.00", payer=0, **extra):
    group_id, users = trip
    return client.post(
        "/expenses",
        json={
            "group_id": group_id,
            "paid_by": users[payer],
            "amount": amount,
            "description": "Dinner",
            **extra,
        },
    )
