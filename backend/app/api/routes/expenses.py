"""Expense endpoints.

Group-scoped routes authorize through the ``Membership`` dependency. The two
single-expense routes have no ``group_id`` in the path, so they load the expense
first and then check membership imperatively — which also means a soft-deleted
expense answers 404 before any group is consulted.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.core.deps import CurrentUser, DbSession, Membership, assert_membership
from app.repositories import notification_repo
from app.schemas.expense import ExpenseCreate, ExpenseOut, ExpensePage, ExpenseUpdate
from app.services import debt_reminder_service, expense_service

router = APIRouter(tags=["Расходы"])


@router.get(
    "/groups/{group_id}/expenses",
    response_model=ExpensePage,
    summary="Расходы группы",
)
def list_group_expenses(
    group_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    _membership: Membership,
    category_id: uuid.UUID | None = Query(default=None, description="Категория"),
    paid_by: uuid.UUID | None = Query(default=None, description="Кто платил"),
    date_from: date | None = Query(default=None, description="С какой даты"),
    date_to: date | None = Query(default=None, description="По какую дату"),
    q: str | None = Query(
        default=None, max_length=160, description="Поиск по названию и заметке"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Сколько расходов вернуть"),
    offset: int = Query(default=0, ge=0, description="Сколько расходов пропустить"),
) -> ExpensePage:
    return expense_service.list_expenses(
        db,
        group_id=group_id,
        user_id=user.id,
        category_id=category_id,
        paid_by=paid_by,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить расход",
)
def create_group_expense(
    group_id: uuid.UUID,
    payload: ExpenseCreate,
    db: DbSession,
    user: CurrentUser,
    membership: Membership,
    background_tasks: BackgroundTasks,
) -> ExpenseOut:
    expense = expense_service.create_expense(
        db,
        group=membership.group,
        actor=user,
        title=payload.title,
        description=payload.description,
        amount_cents=payload.amount_cents,
        category_id=payload.category_id,
        paid_by=payload.paid_by,
        occurred_at=payload.occurred_at,
        split_mode=payload.split_mode,
        participants=payload.participants,
    )
    # The reminder rows (with a deterministic fallback message already in them)
    # are already committed above. Wording them with Qwen instead happens here,
    # after the response is on its way — the request never waits on Ollama.
    notification_ids = notification_repo.ids_for_expense(db, expense.id)
    if notification_ids:
        background_tasks.add_task(debt_reminder_service.enhance_with_qwen, notification_ids)
    return expense_service.build_expense_out(expense, user.id)


@router.get(
    "/expenses/{expense_id}", response_model=ExpenseOut, summary="Открыть расход"
)
def get_expense(expense_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ExpenseOut:
    expense = expense_service.get_expense(db, expense_id)
    assert_membership(db, expense.group_id, user.id)
    return expense_service.build_expense_out(expense, user.id)


@router.patch(
    "/expenses/{expense_id}", response_model=ExpenseOut, summary="Изменить расход"
)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    db: DbSession,
    user: CurrentUser,
) -> ExpenseOut:
    expense = expense_service.get_expense(db, expense_id)
    assert_membership(db, expense.group_id, user.id)
    expense = expense_service.update_expense(
        db,
        expense=expense,
        actor=user,
        title=payload.title,
        description=payload.description,
        amount_cents=payload.amount_cents,
        category_id=payload.category_id,
        paid_by=payload.paid_by,
        occurred_at=payload.occurred_at,
        split_mode=payload.split_mode,
        participants=payload.participants,
        fields_set=payload.model_fields_set,
    )
    return expense_service.build_expense_out(expense, user.id)


@router.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить расход",
)
def delete_expense(expense_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    expense = expense_service.get_expense(db, expense_id)
    assert_membership(db, expense.group_id, user.id)
    expense_service.delete_expense(db, expense=expense, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
