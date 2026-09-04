from __future__ import annotations

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk


class Category(Base):
    """Expense category. ``icon`` is a Lucide icon name in PascalCase."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Category {self.slug}>"


#: Canonical seed set. ``ensure_categories`` in ``app.db.seed`` keeps the table in
#: sync with this list, so it is safe to run on every startup.
DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("food", "Кафе и рестораны", "UtensilsCrossed"),
    ("groceries", "Продукты", "ShoppingCart"),
    ("housing", "Жильё", "Home"),
    ("rent", "Аренда", "KeyRound"),
    ("utilities", "ЖКХ", "Zap"),
    ("transport", "Транспорт", "Car"),
    ("travel", "Путешествия", "Plane"),
    ("entertainment", "Развлечения", "Film"),
    ("shopping", "Покупки", "ShoppingBag"),
    ("health", "Здоровье", "HeartPulse"),
    ("subscriptions", "Подписки", "Repeat"),
    ("other", "Другое", "CircleEllipsis"),
)


__all__ = ["DEFAULT_CATEGORIES", "Category"]
