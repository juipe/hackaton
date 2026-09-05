"""Money split engine.

Turns an expense total plus one raw input per participant into exact integer-cent
shares. Every proportional mode goes through the same largest-remainder
distribution, so the shares always sum to the expense total: no cent is invented
and none is lost. The module is pure — no database, no HTTP, no floats.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext

from app.core.errors import BadRequest, UnprocessableEntity
from app.models.expense import SplitMode

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)

# Weights carry at most 25 significant digits (``Numeric(25, 6)`` — wide enough for
# an "exact" input_value to hold a whole BigInteger cents amount, not just a
# percentage or a share count) and amounts stay far inside 10**15 cents, so 60
# digits gives the intermediate quotients much more
# precision than the remainder ordering can ever need. Pinning it in a local context
# also keeps the result independent of whatever precision the caller runs under.
_PRECISION = 60


@dataclass(frozen=True)
class SplitInput:
    """One participant's raw input.

    ``value`` is ``None`` for equal, whole cents for exact, a percent for
    percentage and a share count for shares.
    """

    user_id: uuid.UUID
    value: Decimal | None


@dataclass(frozen=True)
class SplitResult:
    """A computed share. ``input_value`` is what the edit form re-hydrates from."""

    user_id: uuid.UUID
    input_value: Decimal | None
    calculated_amount_cents: int


def compute_splits(
    amount_cents: int, mode: SplitMode, participants: list[SplitInput]
) -> list[SplitResult]:
    """Compute each participant's share, in the order they were given."""
    if not participants:
        raise UnprocessableEntity("Добавьте хотя бы одного участника")
    if amount_cents <= 0:
        raise UnprocessableEntity("Сумма должна быть больше нуля")

    seen: set[uuid.UUID] = set()
    for participant in participants:
        if participant.user_id in seen:
            raise UnprocessableEntity("Участник указан дважды")
        seen.add(participant.user_id)

    mode_value = mode.value if isinstance(mode, SplitMode) else str(mode)
    builder = _BUILDERS.get(mode_value)
    if builder is None:
        raise BadRequest("Неизвестный способ деления")

    results = builder(amount_cents, participants)

    if sum(result.calculated_amount_cents for result in results) != amount_cents:
        raise UnprocessableEntity("Расчёт долей не сошёлся")
    return results


def _distribute(amount_cents: int, weights: list[Decimal]) -> list[int]:
    """Split ``amount_cents`` proportionally to ``weights``, largest remainder first.

    Every share is floored, then the leftover cents go to the largest fractional
    remainders with ties broken by position, so the total is exactly
    ``amount_cents``. Callers guarantee a strictly positive weight total.
    """
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        total_weight = sum(weights, _ZERO)
        if total_weight <= _ZERO:
            raise UnprocessableEntity("Расчёт долей не сошёлся")
        amount = Decimal(amount_cents)
        raw = [amount * weight / total_weight for weight in weights]
        floors = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
        leftover = amount_cents - sum(floors)
        if leftover > 0:
            # ``floors[i] - raw[i]`` is the negated fractional part, so ascending
            # order puts the biggest remainder first and keeps index order for ties.
            ranked = sorted(range(len(weights)), key=lambda i: (floors[i] - raw[i], i))
            for index in ranked[:leftover]:
                floors[index] += 1
    return floors


def _split_equal(amount_cents: int, participants: list[SplitInput]) -> list[SplitResult]:
    base, leftover = divmod(amount_cents, len(participants))
    return [
        SplitResult(
            user_id=participant.user_id,
            input_value=None,
            calculated_amount_cents=base + 1 if index < leftover else base,
        )
        for index, participant in enumerate(participants)
    ]


def _split_exact(amount_cents: int, participants: list[SplitInput]) -> list[SplitResult]:
    values = _required_values(participants, "Укажите точную сумму для каждого участника")
    for value in values:
        if _is_negative(value):
            raise UnprocessableEntity("Суммы не могут быть отрицательными")
    for value in values:
        if not _is_whole(value):
            raise UnprocessableEntity("Точные суммы указываются в копейках, без дробей")
    if sum(values, _ZERO) != Decimal(amount_cents):
        raise UnprocessableEntity("Сумма частей должна совпадать с общей суммой")
    return [
        SplitResult(
            user_id=participant.user_id,
            input_value=value,
            calculated_amount_cents=int(value),
        )
        for participant, value in zip(participants, values, strict=True)
    ]


def _split_percentage(
    amount_cents: int, participants: list[SplitInput]
) -> list[SplitResult]:
    values = _required_values(participants, "Укажите процент для каждого участника")
    for value in values:
        if _is_negative(value):
            raise UnprocessableEntity("Проценты не могут быть отрицательными")
    if sum(values, _ZERO) != _HUNDRED:
        raise UnprocessableEntity("Сумма процентов должна быть 100%")
    return _build(participants, values, _distribute(amount_cents, values))


def _split_shares(amount_cents: int, participants: list[SplitInput]) -> list[SplitResult]:
    values = _required_values(participants, "Укажите число долей для каждого участника")
    for value in values:
        if _is_negative(value):
            raise UnprocessableEntity("Доли не могут быть отрицательными")
    for value in values:
        if not _is_whole(value):
            raise UnprocessableEntity("Доли должны быть целыми числами")
    if sum(values, _ZERO) == _ZERO:
        raise UnprocessableEntity("Сумма долей должна быть больше нуля")
    return _build(participants, values, _distribute(amount_cents, values))


def _build(
    participants: list[SplitInput], values: list[Decimal], amounts: list[int]
) -> list[SplitResult]:
    return [
        SplitResult(
            user_id=participant.user_id,
            input_value=value,
            calculated_amount_cents=amount,
        )
        for participant, value, amount in zip(participants, values, amounts, strict=True)
    ]


def _required_values(participants: list[SplitInput], message: str) -> list[Decimal]:
    values: list[Decimal] = []
    for participant in participants:
        if participant.value is None:
            raise UnprocessableEntity(message)
        values.append(participant.value)
    return values


def _is_negative(value: Decimal) -> bool:
    # A NaN would raise ``InvalidOperation`` under ``<``; it is not negative, and the
    # whole-number and total checks reject it right after this.
    return not value.is_nan() and value < _ZERO


def _is_whole(value: Decimal) -> bool:
    return value.is_finite() and value == value.to_integral_value()


_BUILDERS: dict[str, Callable[[int, list[SplitInput]], list[SplitResult]]] = {
    SplitMode.EQUAL.value: _split_equal,
    SplitMode.EXACT.value: _split_exact,
    SplitMode.PERCENTAGE.value: _split_percentage,
    SplitMode.SHARES.value: _split_shares,
}


__all__ = ["SplitInput", "SplitResult", "compute_splits"]
