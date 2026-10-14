from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Group, GroupMember, User


def get_group(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(404, "Group not found")
    return group


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


def group_members(db: Session, group_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
            .order_by(User.id)
        )
    )


def require_member(db: Session, group_id: int, user_id: int):
    if db.get(GroupMember, (group_id, user_id)) is None:
        raise HTTPException(422, f"User {user_id} is not a member of this group")
