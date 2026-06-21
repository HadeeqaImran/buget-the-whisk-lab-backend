from datetime import date
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db, init_db
from app.errors import (
    database_exception_handler,
    http_exception_handler,
    integrity_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.models import BudgetEntry, Category, Family, FamilyMembership, User
from app.schemas import (
    BudgetSummary,
    CategoryCreate,
    CategoryRead,
    CategoryReorderItem,
    CategoryUpdate,
    EntryCreate,
    EntryMove,
    EntryRead,
    EntryUpdate,
    FamilyCreate,
    FamilyInvite,
    FamilyMemberRead,
    FamilyRead,
    FamilyUpdate,
    MeRead,
    TokenRead,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)

app = FastAPI(title="Household Budget API", version="1.0.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_families(db: Session, user: User) -> list[Family]:
    return list(
        db.scalars(
            select(Family)
            .join(FamilyMembership, FamilyMembership.family_id == Family.id)
            .where(FamilyMembership.user_id == user.id)
            .order_by(Family.created_at)
        )
    )


def require_family(db: Session, user: User, family_id: int | None = None) -> Family:
    statement = (
        select(Family)
        .join(FamilyMembership, FamilyMembership.family_id == Family.id)
        .where(FamilyMembership.user_id == user.id)
        .order_by(Family.created_at)
    )
    if family_id is not None:
        statement = statement.where(Family.id == family_id)

    family = db.scalar(statement)
    if family is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Family access denied")
    return family


def require_owner_membership(db: Session, user: User, family_id: int) -> FamilyMembership:
    membership = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Family access denied")
    if membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only family owners can do this")
    return membership


def require_category(db: Session, user: User, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if category.family_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Category is not assigned to a family")
    require_family(db, user, category.family_id)
    return category


def require_entry(db: Session, user: User, entry_id: int) -> BudgetEntry:
    entry = db.scalar(
        select(BudgetEntry)
        .join(Category, Category.id == BudgetEntry.category_id)
        .where(BudgetEntry.id == entry_id)
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    require_category(db, user, entry.category_id)
    return entry


def create_default_family(db: Session, user: User) -> Family:
    family = Family(name=f"{user.name}'s Family", created_by_user_id=user.id)
    db.add(family)
    db.flush()
    db.add(FamilyMembership(user_id=user.id, family_id=family.id, role="owner"))
    return family


@app.post("/auth/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenRead:
    email = normalize_email(payload.email)
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    create_default_family(db, user)
    db.commit()
    db.refresh(user)
    return TokenRead(access_token=create_access_token(user.id), user=user)


@app.post("/auth/login", response_model=TokenRead)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenRead:
    email = normalize_email(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenRead(access_token=create_access_token(user.id), user=user)


@app.get("/auth/me", response_model=MeRead)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeRead:
    return MeRead(user=current_user, families=get_user_families(db, current_user))


@app.patch("/auth/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    current_user.name = payload.name.strip()
    db.commit()
    db.refresh(current_user)
    return current_user


@app.get("/families", response_model=list[FamilyRead])
def list_families(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Family]:
    return get_user_families(db, current_user)


@app.post("/families", response_model=FamilyRead, status_code=status.HTTP_201_CREATED)
def create_family(
    payload: FamilyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Family:
    family = Family(name=payload.name.strip(), created_by_user_id=current_user.id)
    db.add(family)
    db.flush()
    db.add(FamilyMembership(user_id=current_user.id, family_id=family.id, role="owner"))
    db.commit()
    db.refresh(family)
    return family


@app.patch("/families/{family_id}", response_model=FamilyRead)
def update_family(
    family_id: int,
    payload: FamilyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Family:
    require_owner_membership(db, current_user, family_id)
    family = require_family(db, current_user, family_id)
    family.name = payload.name.strip()
    db.commit()
    db.refresh(family)
    return family


@app.get("/families/{family_id}/members", response_model=list[FamilyMemberRead])
def list_family_members(
    family_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FamilyMembership]:
    require_family(db, current_user, family_id)
    return list(
        db.scalars(
            select(FamilyMembership)
            .options(selectinload(FamilyMembership.user))
            .where(FamilyMembership.family_id == family_id)
            .order_by(FamilyMembership.created_at)
        )
    )


@app.post("/families/{family_id}/invite", response_model=list[FamilyMemberRead])
def invite_family_member(
    family_id: int,
    payload: FamilyInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FamilyMembership]:
    require_owner_membership(db, current_user, family_id)
    invited_user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if invited_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User must create an account first")

    existing_membership = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == invited_user.id,
        )
    )
    if existing_membership is None:
        db.add(FamilyMembership(user_id=invited_user.id, family_id=family_id, role=payload.role))
        db.commit()

    return list_family_members(family_id, current_user, db)


@app.get("/categories", response_model=list[CategoryRead])
def list_categories(
    family_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Category]:
    family = require_family(db, current_user, family_id)
    return list(
        db.scalars(
            select(Category)
            .options(selectinload(Category.entries))
            .where(Category.family_id == family.id)
            .order_by(Category.type, Category.position, Category.created_at)
        )
    )


@app.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    family_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Category:
    family = require_family(db, current_user, family_id)
    next_position = (
        db.scalar(
            select(func.coalesce(func.max(Category.position), -1)).where(
                Category.type == payload.type,
                Category.family_id == family.id,
            )
        )
        + 1
    )
    category = Category(**payload.model_dump(), family_id=family.id, position=next_position)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@app.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Category:
    category = require_category(db, current_user, category_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@app.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    category = require_category(db, current_user, category_id)
    db.delete(category)
    db.commit()


@app.post("/categories/reorder", response_model=list[CategoryRead])
def reorder_categories(
    payload: list[CategoryReorderItem],
    family_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Category]:
    family = require_family(db, current_user, family_id)
    categories_by_id = {
        category.id: category
        for category in db.scalars(select(Category).where(Category.family_id == family.id))
    }
    for item in payload:
        category = categories_by_id.get(item.id)
        if category is not None:
            category.position = item.position

    db.commit()
    return list_categories(family.id, current_user, db)


@app.post("/entries", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: EntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetEntry:
    category = require_category(db, current_user, payload.category_id)
    next_position = (
        db.scalar(
            select(func.coalesce(func.max(BudgetEntry.position), -1)).where(
                BudgetEntry.category_id == category.id
            )
        )
        + 1
    )
    entry_data = payload.model_dump()
    entry_data["occurrence_date"] = entry_data["occurrence_date"] or date.today()
    entry = BudgetEntry(**entry_data, position=next_position)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.patch("/entries/{entry_id}", response_model=EntryRead)
def update_entry(
    entry_id: int,
    payload: EntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetEntry:
    entry = require_entry(db, current_user, entry_id)

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        require_category(db, current_user, data["category_id"])

    for field, value in data.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry


@app.patch("/entries/{entry_id}/move", response_model=EntryRead)
def move_entry(
    entry_id: int,
    payload: EntryMove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetEntry:
    entry = require_entry(db, current_user, entry_id)
    require_category(db, current_user, payload.category_id)

    entry.category_id = payload.category_id
    entry.position = payload.position
    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entry = require_entry(db, current_user, entry_id)
    db.delete(entry)
    db.commit()


@app.get("/summary", response_model=BudgetSummary)
def get_summary(
    family_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetSummary:
    family = require_family(db, current_user, family_id)
    rows = db.execute(
        select(Category.type, func.coalesce(func.sum(BudgetEntry.amount), 0))
        .outerjoin(BudgetEntry, BudgetEntry.category_id == Category.id)
        .where(Category.family_id == family.id)
        .group_by(Category.type)
    ).all()
    totals = {budget_type: Decimal(amount) for budget_type, amount in rows}
    total_income = totals.get("income", Decimal("0"))
    total_expenses = totals.get("expense", Decimal("0"))
    return BudgetSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        remaining=total_income - total_expenses,
    )
