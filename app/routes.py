import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense, Group, GroupMember, Settlement, User
from app.schemas import (
    AnalyticsOut,
    BalanceOut,
    ExpenseCreate,
    ExpenseOut,
    GroupCreate,
    GroupOut,
    MemberCreate,
    MonthlySummaryOut,
    SettlementCreate,
    SettlementOut,
    SuggestionsOut,
    UserCreate,
    UserOut,
)
from app.services.balances import (
    balance_view,
    create_settlement,
    settlement_view,
    suggestions_view,
)
from app.services.common import get_group, get_user, group_members
from app.services.expenses import create_expense, expense_views
from app.services.money import format_money

router = APIRouter()
DB = Annotated[Session, Depends(get_db, scope="function")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
# India does not observe daylight saving time, so this works without an external time-zone database.
INDIA = timezone(timedelta(hours=5, minutes=30))


@router.get("/health", tags=["Start here"], summary="Check that the service is running")
def health(db: DB):
    db.execute(select(1))
    return {"status": "ok"}


@router.post(
    "/users", response_model=UserOut, status_code=201, tags=["1. People"], summary="Create a person"
)
def add_user(data: UserCreate, db: DB):
    user = User(name=data.name)
    db.add(user)
    db.flush()
    return user


@router.get("/users", response_model=list[UserOut], tags=["1. People"], summary="List people")
def list_users(db: DB, limit: Limit = 100, offset: Offset = 0):
    return db.scalars(select(User).order_by(User.id).limit(limit).offset(offset)).all()


@router.post(
    "/groups",
    response_model=GroupOut,
    status_code=201,
    tags=["2. Groups"],
    summary="Create a group",
)
def add_group(data: GroupCreate, db: DB):
    group = Group(name=data.name, currency=data.currency)
    db.add(group)
    db.flush()
    return group


@router.get("/groups", response_model=list[GroupOut], tags=["2. Groups"], summary="List groups")
def list_groups(db: DB, limit: Limit = 100, offset: Offset = 0):
    return db.scalars(select(Group).order_by(Group.id).limit(limit).offset(offset)).all()


@router.post(
    "/groups/{group_id}/members",
    response_model=UserOut,
    status_code=201,
    tags=["2. Groups"],
    summary="Add a person to a group",
)
def add_member(group_id: int, data: MemberCreate, db: DB):
    get_group(db, group_id)
    user = get_user(db, data.user_id)
    if db.get(GroupMember, (group_id, user.id)):
        raise HTTPException(409, "User already belongs to this group")
    db.add(GroupMember(group_id=group_id, user_id=user.id))
    db.flush()
    return user


@router.get(
    "/groups/{group_id}/members",
    response_model=list[UserOut],
    tags=["2. Groups"],
    summary="List a group's members",
)
def list_members(group_id: int, db: DB):
    get_group(db, group_id)
    return group_members(db, group_id)


@router.post(
    "/expenses",
    response_model=ExpenseOut,
    status_code=201,
    tags=["3. Expenses"],
    summary="Add a shared bill",
)
def add_expense(data: ExpenseCreate, db: DB):
    return expense_views(db, [create_expense(db, data)])[0]


@router.get(
    "/groups/{group_id}/expenses",
    response_model=list[ExpenseOut],
    tags=["3. Expenses"],
    summary="View a group's expense history",
)
def list_expenses(
    group_id: int,
    db: DB,
    limit: Limit = 100,
    offset: Offset = 0,
    category: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    get_group(db, group_id)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must not be after date_to")
    query = select(Expense).where(Expense.group_id == group_id)
    if category is not None:
        query = query.where(Expense.category == category)
    if q is not None:
        query = query.where(Expense.description.icontains(q, autoescape=True))
    if date_from:
        query = query.where(Expense.created_at >= datetime.combine(date_from, time.min))
    if date_to and date_to < date.max:
        query = query.where(
            Expense.created_at < datetime.combine(date_to + timedelta(days=1), time.min)
        )
    expenses = list(
        db.scalars(
            query.order_by(Expense.created_at.desc(), Expense.id.desc()).limit(limit).offset(offset)
        )
    )
    return expense_views(db, expenses)


@router.get(
    "/groups/{group_id}/monthly-summary",
    response_model=list[MonthlySummaryOut],
    tags=["3. Expenses"],
    summary="See spending totals for each month",
)
def monthly_summary(group_id: int, db: DB):
    """Monthly totals are calculated from the recorded expenses and do not store duplicate data."""
    get_group(db, group_id)
    totals: dict[str, list[int]] = {}
    for expense in db.scalars(select(Expense).where(Expense.group_id == group_id)):
        month = expense.created_at.strftime("%Y-%m")
        row = totals.setdefault(month, [0, 0])
        row[0] += expense.amount_minor
        row[1] += 1
    return [
        {"month": month, "total_spent": format_money(total), "expense_count": count}
        for month, (total, count) in sorted(totals.items(), reverse=True)
    ]


@router.get(
    "/groups/{group_id}/analytics",
    response_model=AnalyticsOut,
    tags=["3. Expenses"],
    summary="See spending by category and payer",
)
def analytics(group_id: int, db: DB):
    group = get_group(db, group_id)
    expenses = list(db.scalars(select(Expense).where(Expense.group_id == group_id)))
    users = {user.id: user.name for user in group_members(db, group_id)}
    categories: dict[str, list[int]] = {}
    payers: dict[str, list[int]] = {}
    for expense in expenses:
        for buckets, name in (
            (categories, expense.category or "Other"),
            (payers, users[expense.paid_by]),
        ):
            row = buckets.setdefault(name, [0, 0])
            row[0] += expense.amount_minor
            row[1] += 1

    def buckets(values: dict[str, list[int]]):
        return [
            {"name": name, "total": format_money(total), "expense_count": count}
            for name, (total, count) in sorted(
                values.items(), key=lambda item: (-item[1][0], item[0])
            )
        ]

    return {
        "group_id": group_id,
        "currency": group.currency,
        "total_spent": format_money(sum(expense.amount_minor for expense in expenses)),
        "expense_count": len(expenses),
        "by_category": buckets(categories),
        "by_payer": buckets(payers),
    }


@router.get(
    "/groups/{group_id}/expenses/export.csv",
    tags=["3. Expenses"],
    summary="Download the expense history as a CSV file",
    response_class=Response,
)
def export_expenses_csv(group_id: int, db: DB):
    get_group(db, group_id)
    expenses = list(
        db.scalars(
            select(Expense)
            .where(Expense.group_id == group_id)
            .order_by(Expense.created_at.desc(), Expense.id.desc())
        )
    )
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Category", "Paid by", "Amount (INR)", "Split type"])
    for expense in expense_views(db, expenses):
        created_at = datetime.fromisoformat(expense["created_at"].removesuffix("Z")).replace(
            tzinfo=timezone.utc
        )
        writer.writerow(
            [
                created_at.astimezone(INDIA).date().isoformat(),
                expense["description"],
                expense["category"] or "Other",
                expense["payer_name"],
                expense["amount"],
                expense["split_type"],
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="group-{group_id}-expenses.csv"'},
    )


@router.get(
    "/balances",
    response_model=BalanceOut,
    tags=["4. Settle up"],
    summary="See what each person paid, owes, or is owed",
)
def balances(db: DB, group_id: Annotated[int, Query(gt=0)]):
    """Pairwise ledger balances and member net positions. Positive net means receivable."""
    return balance_view(db, group_id)


@router.get(
    "/groups/{group_id}/settlement-suggestions",
    response_model=SuggestionsOut,
    tags=["4. Settle up"],
    summary="Get the simplest suggested repayments",
)
def suggestions(group_id: int, db: DB):
    """Suggested payments clear group net balances; no records are changed."""
    return suggestions_view(db, group_id)


@router.post(
    "/groups/{group_id}/settlements",
    response_model=SettlementOut,
    status_code=201,
    tags=["4. Settle up"],
    summary="Record money that has been paid back",
)
def add_settlement(group_id: int, data: SettlementCreate, db: DB):
    return settlement_view(create_settlement(db, group_id, data))


@router.get(
    "/groups/{group_id}/settlements",
    response_model=list[SettlementOut],
    tags=["4. Settle up"],
    summary="View recorded repayments",
)
def list_settlements(group_id: int, db: DB, limit: Limit = 100, offset: Offset = 0):
    get_group(db, group_id)
    return [
        settlement_view(payment)
        for payment in db.scalars(
            select(Settlement)
            .where(Settlement.group_id == group_id)
            .order_by(Settlement.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]
