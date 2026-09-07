"""Русский формат чисел в долях участников: «100,5», «1 000,50», «60 ₽».

Схема запроса (``schemas.expense._to_decimal``) обязана принимать те же
строки, что и ``utils.money.str_to_cents`` — запятую как десятичный
разделитель, пробелы-разряды и знак рубля. Ловит регресс, при котором ввод
с запятой валился 422-й «Доля участника должна быть числом».
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.group import Group
from app.models.user import User


@pytest.fixture()
def world(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> tuple[User, User, Group]:
    ada = make_user(name="Ada")
    ben = make_user(name="Ben")
    group = group_factory(ada, name="Обеды", currency="RUB", members=[ben])
    return ada, ben, group


def _post(
    client: TestClient,
    group: Group,
    *,
    category: Category,
    paid_by: User,
    split_mode: str,
    amount_cents: int,
    participants: list[tuple[User, Any]],
):
    return client.post(
        f"/api/groups/{group.id}/expenses",
        json={
            "title": "Обед",
            "amount_cents": amount_cents,
            "category_id": str(category.id),
            "paid_by": str(paid_by.id),
            "split_mode": split_mode,
            "participants": [
                {"user_id": str(user.id), "value": value} for user, value in participants
            ],
        },
    )


@pytest.fixture()
def food(categories: list[Category]) -> Category:
    return next(category for category in categories if category.slug == "food")


def test_exact_split_accepts_spaced_and_currency_marked_values(
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
    food: Category,
) -> None:
    ada, ben, group = world
    # Точные доли задаются в копейках; «6 050» и «100 050 ₽» должны
    # пережить пробелы-разряды и знак рубля.
    response = _post(
        api_client(ada),
        group,
        category=food,
        paid_by=ada,
        split_mode="exact",
        amount_cents=106_100,
        participants=[(ada, "6 050"), (ben, "100 050 ₽")],
    )
    assert response.status_code == 201, response.text
    shares = {
        split["user_id"]: split["calculated_amount_cents"]
        for split in response.json()["splits"]
    }
    assert shares[str(ada.id)] == 6_050
    assert shares[str(ben.id)] == 100_050


def test_percentage_split_accepts_comma_decimals(
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
    food: Category,
) -> None:
    ada, ben, group = world
    response = _post(
        api_client(ada),
        group,
        category=food,
        paid_by=ada,
        split_mode="percentage",
        amount_cents=10_000,
        participants=[(ada, "60,5"), (ben, "39,5")],
    )
    assert response.status_code == 201, response.text


def test_garbage_value_is_still_rejected_with_the_russian_message(
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
    food: Category,
) -> None:
    ada, ben, group = world
    response = _post(
        api_client(ada),
        group,
        category=food,
        paid_by=ada,
        split_mode="exact",
        amount_cents=10_000,
        participants=[(ada, "сто"), (ben, "100")],
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Доля участника должна быть числом"
