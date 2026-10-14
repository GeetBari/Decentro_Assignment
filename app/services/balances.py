"""Derive balances from the ledger; never maintain a second balance table."""

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit, Settlement
from app.schemas import SettlementCreate
from app.services.common import get_group, group_members, require_member
from app.services.money import format_money, to_minor


def ledger(db: Session, group_id: int):
    group = get_group(db, group_id)
    members = {member.id: member for member in group_members(db, group_id)}
    totals = {
        user_id: {"paid": 0, "share": 0, "settled_out": 0, "settled_in": 0} for user_id in members
    }
    pairs = defaultdict(int)

    def add_debt(debtor, creditor, amount):
        if debtor == creditor:
            return
        low, high = sorted((debtor, creditor))
        pairs[low, high] += amount if debtor == low else -amount

    for expense in db.scalars(select(Expense).where(Expense.group_id == group_id)):
        totals[expense.paid_by]["paid"] += expense.amount_minor
    for split, payer in db.execute(
        select(ExpenseSplit, Expense.paid_by)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id)
    ):
        totals[split.user_id]["share"] += split.amount_minor
        add_debt(split.user_id, payer, split.amount_minor)
    for payment in db.scalars(select(Settlement).where(Settlement.group_id == group_id)):
        totals[payment.from_user_id]["settled_out"] += payment.amount_minor
        totals[payment.to_user_id]["settled_in"] += payment.amount_minor
        add_debt(payment.from_user_id, payment.to_user_id, -payment.amount_minor)
    net = {
        user_id: row["paid"] - row["share"] + row["settled_out"] - row["settled_in"]
        for user_id, row in totals.items()
    }
    return group, members, totals, pairs, net


def transfer(members, debtor, creditor, amount):
    return {
        "from_user_id": debtor,
        "from_name": members[debtor].name,
        "to_user_id": creditor,
        "to_name": members[creditor].name,
        "amount": format_money(amount),
    }


def balance_view(db: Session, group_id: int):
    group, members, totals, pairs, net = ledger(db, group_id)
    return {
        "group_id": group.id,
        "currency": group.currency,
        "is_settled": all(amount == 0 for amount in net.values()),
        "balances": [
            transfer(members, low if amount > 0 else high, high if amount > 0 else low, abs(amount))
            for (low, high), amount in sorted(pairs.items())
            if amount
        ],
        "members": [
            {
                "user_id": user_id,
                "name": member.name,
                **{key: format_money(value) for key, value in totals[user_id].items()},
                "net_balance": format_money(net[user_id]),
            }
            for user_id, member in members.items()
        ],
    }


def suggest_transfers(net: dict[int, int]) -> list[tuple[int, int, int]]:
    """Largest balances first, stable ID tie-break; at most debtors+creditors-1 transfers."""
    debtors = sorted(
        ((user_id, -amount) for user_id, amount in net.items() if amount < 0),
        key=lambda item: (-item[1], item[0]),
    )
    creditors = sorted(
        ((user_id, amount) for user_id, amount in net.items() if amount > 0),
        key=lambda item: (-item[1], item[0]),
    )
    if sum(net.values()) != 0:
        raise ValueError("Net balances must sum to zero")
    result = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        amount = min(debt, credit)
        result.append((debtor, creditor, amount))
        debtors[i] = (debtor, debt - amount)
        creditors[j] = (creditor, credit - amount)
        if debt == amount:
            i += 1
        if credit == amount:
            j += 1
    return result


def suggestions_view(db: Session, group_id: int):
    group, members, _, _, net = ledger(db, group_id)
    suggestions = [transfer(members, *item) for item in suggest_transfers(net)]
    return {
        "group_id": group.id,
        "currency": group.currency,
        "suggestions": suggestions,
        "payment_count": len(suggestions),
        "algorithm": "greedy_net_balances",
    }


def create_settlement(db: Session, group_id: int, data: SettlementCreate):
    get_group(db, group_id)
    require_member(db, group_id, data.from_user_id)
    require_member(db, group_id, data.to_user_id)
    *_, net = ledger(db, group_id)
    amount = to_minor(data.amount)
    available = min(-net[data.from_user_id], net[data.to_user_id])
    if amount > available:
        raise HTTPException(
            422,
            "Payment must go from a net debtor to a net creditor and not exceed either outstanding balance",
        )
    payment = Settlement(
        group_id=group_id,
        from_user_id=data.from_user_id,
        to_user_id=data.to_user_id,
        amount_minor=amount,
    )
    db.add(payment)
    db.flush()
    return payment


def settlement_view(payment: Settlement):
    return {
        "id": payment.id,
        "group_id": payment.group_id,
        "from_user_id": payment.from_user_id,
        "to_user_id": payment.to_user_id,
        "amount": format_money(payment.amount_minor),
        "created_at": payment.created_at.isoformat() + "Z",
    }
