from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now():
    # SQLite stores naive timestamps; all application timestamps are UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    __table_args__ = (CheckConstraint("currency = 'INR'"),)


class GroupMember(Base):
    __tablename__ = "group_members"
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int]
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(50))
    split_type: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    __table_args__ = (
        CheckConstraint("amount_minor > 0 AND amount_minor <= 100000000000"),
        CheckConstraint("split_type IN ('equal', 'unequal')"),
        ForeignKeyConstraint(
            ["group_id", "paid_by"], ["group_members.group_id", "group_members.user_id"]
        ),
        Index("ix_expenses_group_created", "group_id", "created_at", "id"),
    )


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    amount_minor: Mapped[int]
    __table_args__ = (CheckConstraint("amount_minor >= 0"),)


class ExpenseReceipt(Base):
    __tablename__ = "expense_receipts"
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Settlement(Base):
    __tablename__ = "settlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    __table_args__ = (
        CheckConstraint("amount_minor > 0 AND amount_minor <= 100000000000"),
        CheckConstraint("from_user_id != to_user_id"),
        ForeignKeyConstraint(
            ["group_id", "from_user_id"], ["group_members.group_id", "group_members.user_id"]
        ),
        ForeignKeyConstraint(
            ["group_id", "to_user_id"], ["group_members.group_id", "group_members.user_id"]
        ),
        Index("ix_settlements_group", "group_id", "id"),
    )
