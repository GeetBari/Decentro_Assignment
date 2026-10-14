import random

import pytest

from app.services.balances import suggest_transfers
from app.services.money import equal_split, format_money


def test_equal_split_conserves_every_paisa():
    for members in range(1, 20):
        ids = list(range(1, members + 1))
        for amount in [1, 2, 7, 100, 999, 123456789]:
            result = equal_split(amount, ids)
            assert sum(result.values()) == amount
            assert max(result.values()) - min(result.values()) <= 1
            assert equal_split(amount, list(reversed(ids))) == result


@pytest.mark.parametrize("amount,users", [(0, [1]), (1, []), (1, [1, 1])])
def test_invalid_equal_split(amount, users):
    with pytest.raises(ValueError):
        equal_split(amount, users)


def test_format_money():
    assert format_money(-1) == "-0.01"
    assert format_money(100000000000) == "1000000000.00"


def test_suggestions_conserve_positions_and_clear_debts():
    rng = random.Random(42)
    for _ in range(100):
        net = {user: rng.randint(-100000, 100000) for user in range(1, 12)}
        net[12] = -sum(net.values())
        original = net.copy()
        plan = suggest_transfers(net)
        assert net == original
        assert len(plan) <= len([n for n in net.values() if n]) - 1
        for debtor, creditor, amount in plan:
            assert amount > 0 and debtor != creditor
            net[debtor] += amount
            net[creditor] -= amount
        assert all(value == 0 for value in net.values())
    assert suggest_transfers({1: 0, 2: 0}) == []
    with pytest.raises(ValueError):
        suggest_transfers({1: -10, 2: 11})
