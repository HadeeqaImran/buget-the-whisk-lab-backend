from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["FamilyMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_families: Mapped[list["Family"]] = relationship(back_populates="created_by")


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_by: Mapped[User] = relationship(back_populates="created_families")
    memberships: Mapped[list["FamilyMembership"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="family",
        cascade="all, delete-orphan",
    )


class FamilyMembership(Base):
    __tablename__ = "family_memberships"
    __table_args__ = (UniqueConstraint("user_id", "family_id", name="uq_family_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships")
    family: Mapped[Family] = relationship(back_populates="memberships")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(24), nullable=False, default="#a7c7e7")
    monthly_target: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    include_in_totals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    family: Mapped[Family | None] = relationship(back_populates="categories")
    entries: Mapped[list["BudgetEntry"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="BudgetEntry.position",
    )


class BudgetEntry(Base):
    __tablename__ = "budget_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    occurrence_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    category: Mapped[Category] = relationship(back_populates="entries")
