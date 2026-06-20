from datetime import date
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db, init_db
from app.models import BudgetEntry, Category
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
)

app = FastAPI(title="Household Budget API", version="1.0.0")

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


@app.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(
        db.scalars(
            select(Category)
            .options(selectinload(Category.entries))
            .order_by(Category.type, Category.position, Category.created_at)
        )
    )


@app.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> Category:
    next_position = (
        db.scalar(select(func.coalesce(func.max(Category.position), -1)).where(Category.type == payload.type)) + 1
    )
    category = Category(**payload.model_dump(), position=next_position)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@app.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@app.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()


@app.post("/categories/reorder", response_model=list[CategoryRead])
def reorder_categories(payload: list[CategoryReorderItem], db: Session = Depends(get_db)) -> list[Category]:
    categories_by_id = {category.id: category for category in db.scalars(select(Category))}
    for item in payload:
        category = categories_by_id.get(item.id)
        if category is not None:
            category.position = item.position

    db.commit()
    return list_categories(db)


@app.post("/entries", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)) -> BudgetEntry:
    category = db.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    next_position = (
        db.scalar(
            select(func.coalesce(func.max(BudgetEntry.position), -1)).where(
                BudgetEntry.category_id == payload.category_id
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
def update_entry(entry_id: int, payload: EntryUpdate, db: Session = Depends(get_db)) -> BudgetEntry:
    entry = db.get(BudgetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and db.get(Category, data["category_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field, value in data.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry


@app.patch("/entries/{entry_id}/move", response_model=EntryRead)
def move_entry(entry_id: int, payload: EntryMove, db: Session = Depends(get_db)) -> BudgetEntry:
    entry = db.get(BudgetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    entry.category_id = payload.category_id
    entry.position = payload.position
    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: Session = Depends(get_db)) -> None:
    entry = db.get(BudgetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    db.delete(entry)
    db.commit()


@app.get("/summary", response_model=BudgetSummary)
def get_summary(db: Session = Depends(get_db)) -> BudgetSummary:
    rows = db.execute(
        select(Category.type, func.coalesce(func.sum(BudgetEntry.amount), 0))
        .outerjoin(BudgetEntry, BudgetEntry.category_id == Category.id)
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
