from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit, User
from app.schemas import ExpenseCreate
from app.services.common import get_group, group_members
from app.services.money import equal_split, format_money, to_minor


def create_expense(db: Session, data: ExpenseCreate) -> Expense:
    get_group(db, data.group_id)
    members = {member.id for member in group_members(db, data.group_id)}
    if not members:
        raise HTTPException(422, "Cannot add an expense to an empty group")
    if data.paid_by not in members:
        raise HTTPException(422, "Payer must belong to the group")
    amount = to_minor(data.amount)
    if data.splits is None:
        shares = equal_split(amount, list(members))
    else:
        shares = {split.user_id: to_minor(split.amount) for split in data.splits}
        if not shares.keys() <= members:
            raise HTTPException(422, "All split participants must belong to the group")
    expense = Expense(
        group_id=data.group_id,
        paid_by=data.paid_by,
        amount_minor=amount,
        description=data.description,
        category=data.category,
        split_type="equal" if data.splits is None else "unequal",
    )
    db.add(expense)
    db.flush()
    db.add_all(
        [
            ExpenseSplit(expense_id=expense.id, user_id=user_id, amount_minor=share)
            for user_id, share in shares.items()
        ]
    )
    db.flush()
    return expense


def expense_views(db: Session, expenses: list[Expense]) -> list[dict]:
    if not expenses:
        return []
    # Fetch participants for the whole page, rather than one query per expense.
    rows = db.execute(
        select(ExpenseSplit, User)
        .join(User, User.id == ExpenseSplit.user_id)
        .where(ExpenseSplit.expense_id.in_([expense.id for expense in expenses]))
        .order_by(ExpenseSplit.user_id)
    )
    splits: dict[int, list] = {}
    for split, user in rows:
        splits.setdefault(split.expense_id, []).append(
            {
                "user_id": user.id,
                "name": user.name,
                "amount": format_money(split.amount_minor),
            }
        )
    payers = {
        user.id: user.name
        for user in db.scalars(
            select(User).where(User.id.in_({expense.paid_by for expense in expenses}))
        )
    }
    return [
        {
            "id": expense.id,
            "group_id": expense.group_id,
            "paid_by": expense.paid_by,
            "payer_name": payers[expense.paid_by],
            "amount": format_money(expense.amount_minor),
            "description": expense.description,
            "category": expense.category,
            "split_type": expense.split_type,
            "created_at": expense.created_at.isoformat() + "Z",
            "splits": splits[expense.id],
        }
        for expense in expenses
    ]
