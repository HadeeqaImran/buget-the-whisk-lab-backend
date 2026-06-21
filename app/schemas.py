from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BudgetType = Literal["income", "expense"]
FamilyRole = Literal["owner", "member"]


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class FamilyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FamilyUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FamilyRead(BaseModel):
    id: int
    name: str
    created_by_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FamilyMemberRead(BaseModel):
    id: int
    role: FamilyRole
    created_at: datetime
    user: UserRead

    model_config = ConfigDict(from_attributes=True)


class FamilyInvite(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: FamilyRole = "member"


class MeRead(BaseModel):
    user: UserRead
    families: list[FamilyRead]


class EntryBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    occurrence_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class EntryCreate(EntryBase):
    category_id: int


class EntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    occurrence_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    category_id: int | None = None
    position: int | None = Field(default=None, ge=0)


class EntryMove(BaseModel):
    category_id: int
    position: int = Field(ge=0)


class EntryRead(BaseModel):
    id: int
    category_id: int
    title: str
    amount: Decimal
    occurrence_date: date
    notes: str | None
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: BudgetType
    color: str = Field(default="#a7c7e7", max_length=24)
    monthly_target: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=24)
    monthly_target: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    position: int | None = Field(default=None, ge=0)


class CategoryReorderItem(BaseModel):
    id: int
    position: int = Field(ge=0)


class CategoryRead(CategoryBase):
    id: int
    family_id: int | None
    position: int
    created_at: datetime
    entries: list[EntryRead] = []

    model_config = ConfigDict(from_attributes=True)


class BudgetSummary(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    remaining: Decimal
