from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit
from tests.conftest import add_expense


def test_assignment_example(client, trip):
    group, (mohit, rahul, ankit) = trip
    response = add_expense(client, trip)
    assert response.status_code == 201
    expense = response.json()
    assert expense["amount"] == "1200.00"
    assert [(s["user_id"], s["amount"]) for s in expense["splits"]] == [
        (mohit, "400.00"),
        (rahul, "400.00"),
        (ankit, "400.00"),
    ]
    balances = client.get("/balances", params={"group_id": group}).json()
    assert [(b["from_user_id"], b["to_user_id"], b["amount"]) for b in balances["balances"]] == [
        (rahul, mohit, "400.00"),
        (ankit, mohit, "400.00"),
    ]
    assert [m["net_balance"] for m in balances["members"]] == ["800.00", "-400.00", "-400.00"]
    history = client.get(f"/groups/{group}/expenses").json()
    assert history == [expense]


def test_users_groups_and_duplicate_membership(client, trip):
    group, users = trip
    assert len(client.get("/users").json()) == 3
    assert client.get("/groups").json()[0]["currency"] == "INR"
    assert len(client.get(f"/groups/{group}/members").json()) == 3
    assert client.post(f"/groups/{group}/members", json={"user_id": users[0]}).status_code == 409
    assert client.post(f"/groups/{group}/members", json={"user_id": 999}).status_code == 404
    assert client.post("/groups/999/members", json={"user_id": users[0]}).status_code == 404
    assert len(client.get("/users?limit=1&offset=1").json()) == 1
    assert client.get("/users?limit=0").status_code == 422
    assert client.get("/groups?offset=-1").status_code == 422


@pytest.mark.parametrize(
    "amount", [0, -1, "1.001", "NaN", "Infinity", True, "1000000000.01", None, "abc"]
)
def test_invalid_amounts_are_rejected_without_writes(client, trip, amount):
    assert add_expense(client, trip, amount).status_code == 422
    assert client.get(f"/groups/{trip[0]}/expenses").json() == []


@pytest.mark.parametrize(
    "payload", [{"name": " "}, {"name": "x" * 101}, {"name": "A", "unexpected": 1}]
)
def test_invalid_users(client, payload):
    response = client.post("/users", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Validation failed"


def test_payer_group_and_participant_validation(client, trip):
    group, users = trip
    outsider = client.post("/users", json={"name": "Outside"}).json()["id"]
    assert add_expense(client, trip, paid_by=outsider).status_code == 422
    assert add_expense(client, trip, group_id=999).status_code == 404
    empty = client.post("/groups", json={"name": "Empty"}).json()["id"]
    assert add_expense(client, trip, group_id=empty).status_code == 422
    assert (
        add_expense(client, trip, splits=[{"user_id": outsider, "amount": 1200}]).status_code == 422
    )
    assert add_expense(client, trip, paid_by=True).status_code == 422
    assert add_expense(client, trip, description="  ").status_code == 422
    assert client.post("/groups", json={"name": "US", "currency": "USD"}).status_code == 422
    assert client.get(f"/groups/{group}/expenses").json() == []
    assert client.get("/balances", params={"group_id": empty}).json()["members"] == []


def test_rounding_and_membership_snapshot(client, trip):
    group, _ = trip
    expense = add_expense(client, trip, "100.00").json()
    assert [s["amount"] for s in expense["splits"]] == ["33.34", "33.33", "33.33"]
    late = client.post("/users", json={"name": "Late arrival"}).json()["id"]
    client.post(f"/groups/{group}/members", json={"user_id": late})
    assert client.get(f"/groups/{group}/expenses").json() == [expense]
    later = add_expense(client, trip, "100.00").json()
    assert len(later["splits"]) == 4
    assert all(s["amount"] == "25.00" for s in later["splits"])


def test_tiny_expense(client, trip):
    result = add_expense(client, trip, "0.01").json()
    assert [s["amount"] for s in result["splits"]] == ["0.01", "0.00", "0.00"]
    assert client.get("/balances", params={"group_id": trip[0]}).json()["balances"] == []


def test_single_member_and_duplicate_names(client):
    user = client.post("/users", json={"name": "Alex"}).json()["id"]
    group = client.post("/groups", json={"name": "Solo"}).json()["id"]
    client.post(f"/groups/{group}/members", json={"user_id": user})
    assert add_expense(client, (group, [user]), "10").status_code == 201
    assert client.get("/balances", params={"group_id": group}).json()["balances"] == []
    other = client.post("/users", json={"name": "Alex"}).json()["id"]
    client.post(f"/groups/{group}/members", json={"user_id": other})
    add_expense(client, (group, [user, other]), "10")
    balance = client.get("/balances", params={"group_id": group}).json()["balances"][0]
    assert balance["from_user_id"] == other and balance["to_user_id"] == user


def test_opposing_expenses_net_and_groups_are_isolated(client, trip):
    group, users = trip
    add_expense(client, trip)
    add_expense(client, trip, payer=1)
    result = client.get("/balances", params={"group_id": group}).json()
    assert [(b["from_user_id"], b["to_user_id"], b["amount"]) for b in result["balances"]] == [
        (users[2], users[0], "400.00"),
        (users[2], users[1], "400.00"),
    ]
    assert sum(Decimal(m["net_balance"]) for m in result["members"]) == 0
    other = client.post("/groups", json={"name": "Other"}).json()["id"]
    client.post(f"/groups/{other}/members", json={"user_id": users[0]})
    add_expense(client, (other, users), "90")
    assert client.get("/balances", params={"group_id": group}).json() == result


def test_custom_splits(client, trip):
    _, users = trip
    splits = [{"user_id": user, "amount": amount} for user, amount in zip(users, [500, 300, 200])]
    result = add_expense(client, trip, "1000", splits=splits)
    assert result.status_code == 201
    assert result.json()["split_type"] == "unequal"
    assert [s["amount"] for s in result.json()["splits"]] == ["500.00", "300.00", "200.00"]
    # Explicit participants can be a subset, and the payer can pay entirely for another member.
    assert (
        add_expense(client, trip, "10", splits=[{"user_id": users[1], "amount": 10}]).status_code
        == 201
    )


@pytest.mark.parametrize(
    "splits",
    [
        [],
        [{"user_id": 1, "amount": 1}],
        [{"user_id": 1, "amount": 600}, {"user_id": 1, "amount": 600}],
        [{"user_id": 1, "amount": -1}, {"user_id": 2, "amount": 1201}],
    ],
)
def test_invalid_custom_splits(client, trip, splits):
    assert add_expense(client, trip, splits=splits).status_code == 422


def test_history_filters_pagination_and_literal_search(client, trip):
    group, _ = trip
    add_expense(client, trip, description="Dinner 20% off", category="food")
    add_expense(client, trip, description="Taxi", category="transport")
    assert client.get(f"/groups/{group}/expenses?limit=1").json()[0]["description"] == "Taxi"
    assert client.get(f"/groups/{group}/expenses?limit=1&offset=1").json()[0]["category"] == "food"
    assert len(client.get(f"/groups/{group}/expenses?category=food").json()) == 1
    assert len(client.get(f"/groups/{group}/expenses", params={"q": "%"}).json()) == 1
    assert len(client.get(f"/groups/{group}/expenses?q=dINner").json()) == 1
    assert client.get(f"/groups/{group}/expenses?date_from=2099-01-01").json() == []
    assert client.get(f"/groups/{group}/expenses?date_to=2000-01-01").json() == []
    assert (
        client.get(f"/groups/{group}/expenses?date_from=2026-02-01&date_to=2026-01-01").status_code
        == 422
    )
    assert client.get(f"/groups/{group}/expenses?date_from=invalid").status_code == 422


def test_partial_and_full_settlement(client, trip):
    group, (mohit, rahul, ankit) = trip
    add_expense(client, trip)
    path = f"/groups/{group}/settlements"
    payload = {"from_user_id": rahul, "to_user_id": mohit, "amount": "100"}
    assert client.post(path, json=payload).status_code == 201
    balances = client.get("/balances", params={"group_id": group}).json()
    assert balances["balances"][0]["amount"] == "300.00"
    assert client.post(path, json={**payload, "amount": "300"}).status_code == 201
    assert client.post(path, json={**payload, "amount": "0.01"}).status_code == 422
    remaining = client.get("/balances", params={"group_id": group}).json()["balances"]
    assert len(remaining) == 1 and remaining[0]["from_user_id"] == ankit
    assert len(client.get(path).json()) == 2


def test_invalid_settlements(client, trip):
    group, users = trip
    add_expense(client, trip)
    path = f"/groups/{group}/settlements"
    for source, target, amount in [
        (users[0], users[1], 10),
        (users[1], users[1], 10),
        (users[1], users[0], 401),
        (999, users[0], 1),
        (users[1], users[0], 0),
    ]:
        assert (
            client.post(
                path, json={"from_user_id": source, "to_user_id": target, "amount": amount}
            ).status_code
            == 422
        )
    assert client.get(path).json() == []


def test_suggestions_and_cross_pair_settlements(client, trip):
    group, (a, b, c) = trip
    # A owes B 10; B owes C 10. A can pay C directly.
    add_expense(client, trip, "10", payer=1, splits=[{"user_id": a, "amount": 10}])
    add_expense(client, trip, "10", payer=2, splits=[{"user_id": b, "amount": 10}])
    path = f"/groups/{group}/settlement-suggestions"
    first = client.get(path).json()
    assert first["payment_count"] == 1
    payment = first["suggestions"][0]
    assert (payment["from_user_id"], payment["to_user_id"], payment["amount"]) == (a, c, "10.00")
    assert client.get(path).json() == first  # Suggestions do not write to the ledger.
    assert (
        client.post(
            f"/groups/{group}/settlements",
            json={key: payment[key] for key in ["from_user_id", "to_user_id", "amount"]},
        ).status_code
        == 201
    )
    assert client.get(path).json()["suggestions"] == []
    assert all(
        member["net_balance"] == "0.00"
        for member in client.get("/balances", params={"group_id": group}).json()["members"]
    )


def test_simultaneous_settlements_cannot_overpay(client, trip):
    group, (mohit, rahul, _) = trip
    add_expense(client, trip)

    def pay(_):
        return client.post(
            f"/groups/{group}/settlements",
            json={
                "from_user_id": rahul,
                "to_user_id": mohit,
                "amount": 300,
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(pay, range(2))) == [201, 422]
    assert len(client.get(f"/groups/{group}/settlements").json()) == 1


def test_expense_and_splits_roll_back_together(client, trip, monkeypatch):
    original_flush = Session.flush

    def fail_when_saving_splits(session, *args, **kwargs):
        if any(isinstance(record, ExpenseSplit) for record in session.new):
            raise RuntimeError("Simulated failure while saving shares")
        return original_flush(session, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "flush", fail_when_saving_splits)
        with pytest.raises(RuntimeError, match="Simulated failure"):
            add_expense(client, trip)
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(Expense)).all() == []
        assert session.scalars(select(ExpenseSplit)).all() == []


@pytest.mark.parametrize(
    "path",
    [
        "/groups/999/members",
        "/groups/999/expenses",
        "/balances?group_id=999",
        "/groups/999/settlements",
        "/groups/999/settlement-suggestions",
    ],
)
def test_missing_groups_return_404(client, path):
    assert client.get(path).status_code == 404


def test_docs_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/api-guide").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/expenses" in schema["paths"]
    assert "/balances" in schema["paths"]
    assert schema["paths"]["/expenses"]["post"]["summary"] == "Add a shared bill"


def test_dashboard_and_assets_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "Who pays whom" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/missing.js").status_code == 404


def test_group_settled_flag(client, trip):
    group, users = trip
    assert client.get("/balances", params={"group_id": group}).json()["is_settled"]
    add_expense(client, trip)
    assert not client.get("/balances", params={"group_id": group}).json()["is_settled"]
    for user in users[1:]:
        client.post(
            f"/groups/{group}/settlements",
            json={"from_user_id": user, "to_user_id": users[0], "amount": 400},
        )
    result = client.get("/balances", params={"group_id": group}).json()
    assert result["is_settled"] and result["balances"] == []
