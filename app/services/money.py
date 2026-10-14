from decimal import Decimal


def to_minor(amount: Decimal) -> int:
    """Call only after request validation has checked precision and bounds."""
    return int(amount * 100)


def format_money(minor: int) -> str:
    sign = "-" if minor < 0 else ""
    whole, fraction = divmod(abs(minor), 100)
    return f"{sign}{whole}.{fraction:02d}"


def equal_split(amount_minor: int, user_ids: list[int]) -> dict[int, int]:
    if amount_minor <= 0 or not user_ids or len(set(user_ids)) != len(user_ids):
        raise ValueError("A positive amount and distinct participants are required")
    share, remainder = divmod(amount_minor, len(user_ids))
    return {user_id: share + (index < remainder) for index, user_id in enumerate(sorted(user_ids))}
