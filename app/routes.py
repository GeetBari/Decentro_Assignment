from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense, Group, GroupMember, Settlement, User
from app.schemas import (
    BalanceOut,
    ExpenseCreate,
    ExpenseOut,
    GroupCreate,
    GroupOut,
    MemberCreate,
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

router = APIRouter()
DB = Annotated[Session, Depends(get_db, scope="function")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/health", tags=["Health"])
def health(db: DB):
    db.execute(select(1))
    return {"status": "ok"}


@router.post("/users", response_model=UserOut, status_code=201, tags=["Users"])
def add_user(data: UserCreate, db: DB):
    user = User(name=data.name)
    db.add(user)
    db.flush()
    return user


@router.get("/users", response_model=list[UserOut], tags=["Users"])
def list_users(db: DB, limit: Limit = 100, offset: Offset = 0):
    return db.scalars(select(User).order_by(User.id).limit(limit).offset(offset)).all()


@router.post("/groups", response_model=GroupOut, status_code=201, tags=["Groups"])
def add_group(data: GroupCreate, db: DB):
    group = Group(name=data.name, currency=data.currency)
    db.add(group)
    db.flush()
    return group


@router.get("/groups", response_model=list[GroupOut], tags=["Groups"])
def list_groups(db: DB, limit: Limit = 100, offset: Offset = 0):
    return db.scalars(select(Group).order_by(Group.id).limit(limit).offset(offset)).all()


@router.post("/groups/{group_id}/members", response_model=UserOut, status_code=201, tags=["Groups"])
def add_member(group_id: int, data: MemberCreate, db: DB):
    get_group(db, group_id)
    user = get_user(db, data.user_id)
    if db.get(GroupMember, (group_id, user.id)):
        raise HTTPException(409, "User already belongs to this group")
    db.add(GroupMember(group_id=group_id, user_id=user.id))
    db.flush()
    return user


@router.get("/groups/{group_id}/members", response_model=list[UserOut], tags=["Groups"])
def list_members(group_id: int, db: DB):
    get_group(db, group_id)
    return group_members(db, group_id)


@router.post("/expenses", response_model=ExpenseOut, status_code=201, tags=["Expenses"])
def add_expense(data: ExpenseCreate, db: DB):
    return expense_views(db, [create_expense(db, data)])[0]


@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseOut], tags=["Expenses"])
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


@router.get("/balances", response_model=BalanceOut, tags=["Balances"])
def balances(db: DB, group_id: Annotated[int, Query(gt=0)]):
    """Pairwise ledger balances and member net positions. Positive net means receivable."""
    return balance_view(db, group_id)


@router.get(
    "/groups/{group_id}/settlement-suggestions", response_model=SuggestionsOut, tags=["Balances"]
)
def suggestions(group_id: int, db: DB):
    """Suggested payments clear group net balances; no records are changed."""
    return suggestions_view(db, group_id)


@router.post(
    "/groups/{group_id}/settlements",
    response_model=SettlementOut,
    status_code=201,
    tags=["Settlements"],
)
def add_settlement(group_id: int, data: SettlementCreate, db: DB):
    return settlement_view(create_settlement(db, group_id, data))


@router.get(
    "/groups/{group_id}/settlements", response_model=list[SettlementOut], tags=["Settlements"]
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
