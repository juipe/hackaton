"""Unit tests for :mod:`app.services.budget_threshold_service`.

Expenses are inserted directly against the models (like ``test_balance_service.py``
does), so these tests exercise the threshold math and the dedup state machine in
isolation from the expense/payment services that call into it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.notification import Notification
from app.models.user import User
from app.services import budget_threshold_service as svc
from app.utils.time import utcnow


def _add_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    amount_cents: int,
    shares: Sequence[tuple[User, int]],
    category: Category,
) -> Expense:
    expense = Expense(
        group_id=group.id,
        created_by=payer.id,
        title="Expense",
        amount_cents=amount_cents,
        currency=group.currency,
        category_id=category.id,
        paid_by=payer.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.flush()
    for user, share_cents in shares:
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=user.id,
                split_mode=SplitMode.EQUAL.value,
                input_value=None,
                calculated_amount_cents=share_cents,
            )
        )
    db.commit()
    return expense


def _notifications_for(db: Session, user_id) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.user_id == user_id, Notification.type == svc.NOTIFICATION_TYPE
    )
    return list(db.scalars(stmt))


def _food(categories: list[Category]) -> Category:
    return next(category for category in categories if category.slug == "food")


def _debtor_with_exposure(
    db: Session,
    *,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
    debtor_share_cents: int,
) -> tuple[User, Group]:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    _add_expense(
        db,
        group=group,
        payer=payer,
        amount_cents=debtor_share_cents * 2,
        shares=[(payer, debtor_share_cents), (debtor, debtor_share_cents)],
        category=_food(categories),
    )
    return debtor, group


# --------------------------------------------------------------- configuration


def test_no_budget_configured_means_no_check(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=100_000_00,
    )
    assert debtor.monthly_budget_cents is None

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is None
    assert _notifications_for(db, debtor.id) == []


def test_zero_or_negative_budget_is_treated_as_unconfigured(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=100_000_00,
    )
    debtor.monthly_budget_cents = 0
    db.commit()

    assert svc.check_and_notify(db, user_id=debtor.id) is None

    debtor.monthly_budget_cents = -500_00
    db.commit()

    assert svc.check_and_notify(db, user_id=debtor.id) is None
    assert _notifications_for(db, debtor.id) == []


# --------------------------------------------------------------- threshold math


def _set_budget(db: Session, user: User, cents: int) -> None:
    user.monthly_budget_cents = cents
    db.commit()


def test_below_80_percent_creates_no_notification(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=79_00,
    )
    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is None
    assert _notifications_for(db, debtor.id) == []
    assert debtor.budget_alert_state is None


def test_exactly_80_percent_triggers_approaching(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=80_00,
    )
    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is not None
    assert debtor.budget_alert_state == svc.APPROACHING_STATE
    assert result.amount_due_cents == 80_00


def test_between_80_and_100_percent_is_approaching(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=90_00,
    )
    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is not None
    assert debtor.budget_alert_state == svc.APPROACHING_STATE


def test_exactly_100_percent_triggers_exceeded(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=100_00,
    )
    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is not None
    assert debtor.budget_alert_state == svc.EXCEEDED_STATE


def test_above_100_percent_triggers_exceeded(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=150_00,
    )
    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is not None
    assert debtor.budget_alert_state == svc.EXCEEDED_STATE
    assert result.amount_due_cents == 150_00


# --------------------------------------------------------------- multiple groups


def test_exposure_is_aggregated_across_all_groups(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group_a = group_factory(payer, name="Group A", members=[debtor])
    group_b = group_factory(payer, name="Group B", members=[debtor])
    food = _food(categories)

    _add_expense(
        db,
        group=group_a,
        payer=payer,
        amount_cents=100_00,
        shares=[(payer, 50_00), (debtor, 50_00)],
        category=food,
    )
    _add_expense(
        db,
        group=group_b,
        payer=payer,
        amount_cents=100_00,
        shares=[(payer, 50_00), (debtor, 50_00)],
        category=food,
    )

    _set_budget(db, debtor, 100_00)

    result = svc.check_and_notify(db, user_id=debtor.id)

    # 50 + 50 = 100 = exactly the limit -> exceeded, not approaching.
    assert result is not None
    assert result.amount_due_cents == 100_00
    assert debtor.budget_alert_state == svc.EXCEEDED_STATE


# --------------------------------------------------------------- dedup / state transitions


def test_repeated_call_in_same_state_does_not_duplicate(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=90_00,
    )
    _set_budget(db, debtor, 100_00)

    first = svc.check_and_notify(db, user_id=debtor.id)
    second = svc.check_and_notify(db, user_id=debtor.id)

    assert first is not None
    assert second is None
    assert len(_notifications_for(db, debtor.id)) == 1


def test_transition_from_approaching_to_exceeded_creates_new_notification(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    food = _food(categories)
    _set_budget(db, debtor, 100_00)

    _add_expense(
        db,
        group=group,
        payer=payer,
        amount_cents=180_00,
        shares=[(payer, 90_00), (debtor, 90_00)],
        category=food,
    )
    approaching = svc.check_and_notify(db, user_id=debtor.id)
    assert approaching is not None
    assert debtor.budget_alert_state == svc.APPROACHING_STATE

    _add_expense(
        db,
        group=group,
        payer=payer,
        amount_cents=40_00,
        shares=[(payer, 20_00), (debtor, 20_00)],
        category=food,
    )
    exceeded = svc.check_and_notify(db, user_id=debtor.id)

    assert exceeded is not None
    assert debtor.budget_alert_state == svc.EXCEEDED_STATE
    assert len(_notifications_for(db, debtor.id)) == 2


def test_dropping_back_below_threshold_resets_state_without_notification(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    food = _food(categories)
    _set_budget(db, debtor, 100_00)

    _add_expense(
        db,
        group=group,
        payer=payer,
        amount_cents=200_00,
        shares=[(payer, 100_00), (debtor, 100_00)],
        category=food,
    )
    svc.check_and_notify(db, user_id=debtor.id)
    assert debtor.budget_alert_state == svc.EXCEEDED_STATE

    # Debtor settles up, dropping exposure to zero.
    from app.models.payment import Payment

    db.add(
        Payment(
            group_id=group.id,
            from_user_id=debtor.id,
            to_user_id=payer.id,
            amount_cents=100_00,
            currency=group.currency,
            paid_at=utcnow(),
        )
    )
    db.commit()

    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is None
    assert debtor.budget_alert_state is None
    # Still just the one "exceeded" notification from before.
    assert len(_notifications_for(db, debtor.id)) == 1

    # Debt climbs back into "approaching" territory -> a new notification fires.
    _add_expense(
        db,
        group=group,
        payer=payer,
        amount_cents=180_00,
        shares=[(payer, 90_00), (debtor, 90_00)],
        category=food,
    )
    result = svc.check_and_notify(db, user_id=debtor.id)

    assert result is not None
    assert debtor.budget_alert_state == svc.APPROACHING_STATE
    assert len(_notifications_for(db, debtor.id)) == 2


def test_check_and_notify_many_deduplicates_and_is_resilient(
    db: Session,
    group_factory: Callable[..., Group],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    debtor, _ = _debtor_with_exposure(
        db,
        group_factory=group_factory,
        make_user=make_user,
        categories=categories,
        debtor_share_cents=150_00,
    )
    _set_budget(db, debtor, 100_00)

    created = svc.check_and_notify_many(db, [debtor.id, debtor.id])

    assert len(created) == 1
    assert len(_notifications_for(db, debtor.id)) == 1
