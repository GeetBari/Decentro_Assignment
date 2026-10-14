from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def reject_boolean(value):
    if isinstance(value, bool):
        raise ValueError("Money must be a decimal amount, not a boolean")
    return value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]
Amount = Annotated[
    Decimal,
    BeforeValidator(reject_boolean),
    Field(gt=0, le=Decimal("1000000000"), max_digits=12, decimal_places=2, allow_inf_nan=False),
]
Share = Annotated[
    Decimal,
    BeforeValidator(reject_boolean),
    Field(ge=0, le=Decimal("1000000000"), max_digits=12, decimal_places=2, allow_inf_nan=False),
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserCreate(InputModel):
    name: Name


class GroupCreate(InputModel):
    name: Name
    currency: Literal["INR"] = "INR"


class MemberCreate(InputModel):
    user_id: PositiveId


class SplitCreate(InputModel):
    user_id: PositiveId
    amount: Share


class ExpenseCreate(InputModel):
    group_id: PositiveId
    paid_by: PositiveId
    amount: Amount
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
    ) = None
    splits: list[SplitCreate] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_splits(self):
        if self.splits is not None:
            ids = [split.user_id for split in self.splits]
            if len(set(ids)) != len(ids):
                raise ValueError("Each participant may appear only once in splits")
            if sum((split.amount for split in self.splits), Decimal(0)) != self.amount:
                raise ValueError("Custom shares must sum exactly to the expense amount")
        return self


class ReceiptCreate(InputModel):
    filename: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    content_type: Literal["image/jpeg", "image/png", "application/pdf"]
    data_base64: Annotated[str, StringConstraints(min_length=4, max_length=7_000_000)]


class SettlementCreate(InputModel):
    from_user_id: PositiveId
    to_user_id: PositiveId
    amount: Amount

    @model_validator(mode="after")
    def reject_self_payment(self):
        if self.from_user_id == self.to_user_id:
            raise ValueError("A user cannot settle with themselves")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    currency: str


class SplitOut(BaseModel):
    user_id: int
    name: str
    amount: str


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    paid_by: int
    payer_name: str
    amount: str
    description: str
    category: str | None
    split_type: str
    created_at: str
    splits: list[SplitOut]
    receipt_url: str | None


class TransferOut(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: str


class MemberBalanceOut(BaseModel):
    user_id: int
    name: str
    paid: str
    share: str
    settled_out: str
    settled_in: str
    net_balance: str


class BalanceOut(BaseModel):
    group_id: int
    currency: str
    is_settled: bool
    balances: list[TransferOut]
    members: list[MemberBalanceOut]


class SuggestionsOut(BaseModel):
    group_id: int
    currency: str
    suggestions: list[TransferOut]
    payment_count: int
    algorithm: str


class SettlementOut(BaseModel):
    id: int
    group_id: int
    from_user_id: int
    to_user_id: int
    amount: str
    created_at: str


class SpendingBucketOut(BaseModel):
    name: str
    total: str
    expense_count: int


class AnalyticsOut(BaseModel):
    group_id: int
    currency: str
    total_spent: str
    expense_count: int
    by_category: list[SpendingBucketOut]
    by_payer: list[SpendingBucketOut]


class MonthlySummaryOut(BaseModel):
    month: str
    total_spent: str
    expense_count: int
