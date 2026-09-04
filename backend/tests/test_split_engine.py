"""Split engine tests.

Pure math — no database, no fixtures. The invariant every case comes back to is
that the computed cents sum to exactly ``amount_cents`` and never go negative.
"""

from __future__ import annotations

import re
import uuid
from decimal import ROUND_DOWN, Decimal

import pytest

from app.core.errors import BadRequest, UnprocessableEntity
from app.models.expense import SplitMode
from app.services.split_engine import (
    SplitInput,
    SplitResult,
    _distribute,
    compute_splits,
)

CENT = Decimal("0.000001")

MSG_NO_PARTICIPANTS = "Добавьте хотя бы одного участника"
MSG_AMOUNT = "Сумма должна быть больше нуля"
MSG_DUPLICATE = "Участник указан дважды"
MSG_EXACT_REQUIRED = "Укажите точную сумму для каждого участника"
MSG_EXACT_NEGATIVE = "Суммы не могут быть отрицательными"
MSG_EXACT_WHOLE = "Точные суммы указываются в копейках, без дробей"
MSG_EXACT_SUM = "Сумма частей должна совпадать с общей суммой"
MSG_PCT_REQUIRED = "Укажите процент для каждого участника"
MSG_PCT_NEGATIVE = "Проценты не могут быть отрицательными"
MSG_PCT_SUM = "Сумма процентов должна быть 100%"
MSG_SHARES_REQUIRED = "Укажите число долей для каждого участника"
MSG_SHARES_NEGATIVE = "Доли не могут быть отрицательными"
MSG_SHARES_WHOLE = "Доли должны быть целыми числами"
MSG_SHARES_TOTAL = "Сумма долей должна быть больше нуля"
MSG_UNBALANCED = "Расчёт долей не сошёлся"
MSG_UNKNOWN_MODE = "Неизвестный способ деления"


def ids(count: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(count)]


def participants(
    values: list[Decimal | None], user_ids: list[uuid.UUID] | None = None
) -> list[SplitInput]:
    people = user_ids or ids(len(values))
    return [
        SplitInput(user_id=user_id, value=value)
        for user_id, value in zip(people, values, strict=True)
    ]


def amounts(results: list[SplitResult]) -> list[int]:
    return [result.calculated_amount_cents for result in results]


def raises(message: str) -> pytest.RaisesExc[UnprocessableEntity]:
    return pytest.raises(UnprocessableEntity, match=re.escape(message))


def even_percentages(count: int) -> list[Decimal]:
    """``count`` percentages that sum to exactly 100 within 6 decimal places."""
    each = (Decimal(100) / count).quantize(CENT, rounding=ROUND_DOWN)
    return [each] * (count - 1) + [Decimal(100) - each * (count - 1)]


# --------------------------------------------------------------------------- equal


def test_equal_divides_evenly() -> None:
    results = compute_splits(10_000, SplitMode.EQUAL, participants([None] * 4))
    assert amounts(results) == [2_500, 2_500, 2_500, 2_500]
    assert all(result.input_value is None for result in results)


def test_equal_leftover_cents_go_to_the_first_participants_in_order() -> None:
    people = ids(3)
    results = compute_splits(1_000, SplitMode.EQUAL, participants([None] * 3, people))
    assert amounts(results) == [334, 333, 333]
    assert sum(amounts(results)) == 1_000
    assert [result.user_id for result in results] == people


def test_equal_ignores_supplied_values() -> None:
    values: list[Decimal | None] = [Decimal(7), Decimal("-3"), None]
    results = compute_splits(900, SplitMode.EQUAL, participants(values))
    assert amounts(results) == [300, 300, 300]
    assert all(result.input_value is None for result in results)


def test_equal_with_fewer_cents_than_participants() -> None:
    results = compute_splits(3, SplitMode.EQUAL, participants([None] * 4))
    assert amounts(results) == [1, 1, 1, 0]
    assert sum(amounts(results)) == 3


def test_equal_single_participant_takes_everything() -> None:
    results = compute_splits(4_237, SplitMode.EQUAL, participants([None]))
    assert amounts(results) == [4_237]


# --------------------------------------------------------------------------- exact


def test_exact_happy_path_preserves_input_values() -> None:
    values: list[Decimal | None] = [Decimal(5_000), Decimal(4_000), Decimal(3_000)]
    results = compute_splits(12_000, SplitMode.EXACT, participants(values))
    assert amounts(results) == [5_000, 4_000, 3_000]
    assert [result.input_value for result in results] == values


def test_exact_accepts_trailing_zero_decimals() -> None:
    values: list[Decimal | None] = [Decimal("2500.000000"), Decimal("2500.000000")]
    results = compute_splits(5_000, SplitMode.EXACT, participants(values))
    assert amounts(results) == [2_500, 2_500]


def test_exact_mismatch_is_rejected() -> None:
    values: list[Decimal | None] = [Decimal(5_000), Decimal(4_000)]
    with raises(MSG_EXACT_SUM):
        compute_splits(12_000, SplitMode.EXACT, participants(values))


def test_exact_allows_a_zero_amount_participant() -> None:
    values: list[Decimal | None] = [Decimal(12_000), Decimal(0)]
    results = compute_splits(12_000, SplitMode.EXACT, participants(values))
    assert amounts(results) == [12_000, 0]


def test_exact_requires_every_value() -> None:
    values: list[Decimal | None] = [Decimal(5_000), None]
    with raises(MSG_EXACT_REQUIRED):
        compute_splits(5_000, SplitMode.EXACT, participants(values))


def test_exact_rejects_negative_values() -> None:
    values: list[Decimal | None] = [Decimal(15_000), Decimal(-3_000)]
    with raises(MSG_EXACT_NEGATIVE):
        compute_splits(12_000, SplitMode.EXACT, participants(values))


def test_exact_rejects_fractional_cents() -> None:
    values: list[Decimal | None] = [Decimal("2500.5"), Decimal("2499.5")]
    with raises(MSG_EXACT_WHOLE):
        compute_splits(5_000, SplitMode.EXACT, participants(values))


# ---------------------------------------------------------------------- percentage


def test_percentage_clean_thirds_of_a_hundred() -> None:
    values: list[Decimal | None] = [Decimal(50), Decimal(30), Decimal(20)]
    results = compute_splits(12_000, SplitMode.PERCENTAGE, participants(values))
    assert amounts(results) == [6_000, 3_600, 2_400]
    assert [result.input_value for result in results] == values


def test_percentage_two_decimal_thirds() -> None:
    values: list[Decimal | None] = [
        Decimal("33.33"),
        Decimal("33.33"),
        Decimal("33.34"),
    ]
    results = compute_splits(10_000, SplitMode.PERCENTAGE, participants(values))
    assert amounts(results) == [3_333, 3_333, 3_334]
    assert sum(amounts(results)) == 10_000


def test_percentage_six_decimal_thirds_still_lands_on_the_total() -> None:
    values: list[Decimal | None] = [
        Decimal("33.333333"),
        Decimal("33.333333"),
        Decimal("33.333334"),
    ]
    results = compute_splits(1_000, SplitMode.PERCENTAGE, participants(values))
    assert amounts(results) == [333, 333, 334]
    assert sum(amounts(results)) == 1_000


def test_percentage_repeating_decimals_that_do_not_reach_a_hundred() -> None:
    values: list[Decimal | None] = [Decimal("33.333333")] * 3
    with raises(MSG_PCT_SUM):
        compute_splits(1_000, SplitMode.PERCENTAGE, participants(values))


def test_percentage_allows_a_zero_percent_participant() -> None:
    values: list[Decimal | None] = [Decimal(100), Decimal(0)]
    results = compute_splits(7_777, SplitMode.PERCENTAGE, participants(values))
    assert amounts(results) == [7_777, 0]


@pytest.mark.parametrize(
    "values",
    [
        [Decimal(50), Decimal(40)],
        [Decimal(60), Decimal(60)],
        [Decimal("99.999999"), Decimal("0.000000")],
    ],
)
def test_percentage_sum_must_be_exactly_one_hundred(values: list[Decimal]) -> None:
    with raises(MSG_PCT_SUM):
        compute_splits(10_000, SplitMode.PERCENTAGE, participants(list(values)))


def test_percentage_requires_every_value() -> None:
    values: list[Decimal | None] = [Decimal(100), None]
    with raises(MSG_PCT_REQUIRED):
        compute_splits(10_000, SplitMode.PERCENTAGE, participants(values))


def test_percentage_rejects_negative_values() -> None:
    values: list[Decimal | None] = [Decimal(110), Decimal(-10)]
    with raises(MSG_PCT_NEGATIVE):
        compute_splits(10_000, SplitMode.PERCENTAGE, participants(values))


# -------------------------------------------------------------------------- shares


def test_shares_two_to_one_to_one() -> None:
    values: list[Decimal | None] = [Decimal(2), Decimal(1), Decimal(1)]
    results = compute_splits(12_000, SplitMode.SHARES, participants(values))
    assert amounts(results) == [6_000, 3_000, 3_000]
    assert [result.input_value for result in results] == values


def test_shares_needing_remainder_distribution() -> None:
    values: list[Decimal | None] = [Decimal(1), Decimal(1), Decimal(1)]
    results = compute_splits(1_000, SplitMode.SHARES, participants(values))
    assert amounts(results) == [334, 333, 333]
    assert sum(amounts(results)) == 1_000


def test_shares_remainder_follows_the_largest_fraction_not_the_order() -> None:
    # 1000 * 4/7 = 571.43 and 1000 * 3/7 = 428.57, so the second participant has the
    # larger fractional remainder even though it comes later in the list.
    values: list[Decimal | None] = [Decimal(4), Decimal(3)]
    results = compute_splits(1_000, SplitMode.SHARES, participants(values))
    assert amounts(results) == [571, 429]


def test_shares_zero_share_participant_pays_nothing() -> None:
    values: list[Decimal | None] = [Decimal(3), Decimal(0), Decimal(1)]
    results = compute_splits(8_000, SplitMode.SHARES, participants(values))
    assert amounts(results) == [6_000, 0, 2_000]


def test_shares_all_zero_is_rejected() -> None:
    values: list[Decimal | None] = [Decimal(0), Decimal(0), Decimal(0)]
    with raises(MSG_SHARES_TOTAL):
        compute_splits(5_000, SplitMode.SHARES, participants(values))


def test_shares_requires_every_value() -> None:
    values: list[Decimal | None] = [Decimal(1), None]
    with raises(MSG_SHARES_REQUIRED):
        compute_splits(5_000, SplitMode.SHARES, participants(values))


def test_shares_rejects_negative_values() -> None:
    values: list[Decimal | None] = [Decimal(3), Decimal(-1)]
    with raises(MSG_SHARES_NEGATIVE):
        compute_splits(5_000, SplitMode.SHARES, participants(values))


def test_shares_rejects_fractional_values() -> None:
    values: list[Decimal | None] = [Decimal("1.5"), Decimal("2.5")]
    with raises(MSG_SHARES_WHOLE):
        compute_splits(5_000, SplitMode.SHARES, participants(values))


# ------------------------------------------------------------------ shared guards


@pytest.mark.parametrize("mode", list(SplitMode))
def test_empty_participants_is_rejected_for_every_mode(mode: SplitMode) -> None:
    with raises(MSG_NO_PARTICIPANTS):
        compute_splits(10_000, mode, [])


@pytest.mark.parametrize("mode", list(SplitMode))
@pytest.mark.parametrize("amount_cents", [0, -1, -12_345])
def test_non_positive_amount_is_rejected_for_every_mode(
    mode: SplitMode, amount_cents: int
) -> None:
    with raises(MSG_AMOUNT):
        compute_splits(amount_cents, mode, participants([Decimal(1), Decimal(1)]))


@pytest.mark.parametrize("mode", list(SplitMode))
def test_duplicate_participant_is_rejected_for_every_mode(mode: SplitMode) -> None:
    repeated = uuid.uuid4()
    people = [repeated, uuid.uuid4(), repeated]
    with raises(MSG_DUPLICATE):
        compute_splits(10_000, mode, participants([Decimal(1)] * 3, people))


def test_string_split_mode_is_accepted() -> None:
    results = compute_splits(1_000, "equal", participants([None] * 2))  # type: ignore[arg-type]
    assert amounts(results) == [500, 500]


def test_unknown_split_mode_is_rejected() -> None:
    with pytest.raises(BadRequest, match=re.escape(MSG_UNKNOWN_MODE)):
        compute_splits(1_000, "weighted", participants([None] * 2))  # type: ignore[arg-type]


def test_distribute_rejects_a_zero_weight_total() -> None:
    with raises(MSG_UNBALANCED):
        _distribute(1_000, [Decimal(0), Decimal(0)])


def test_results_keep_participant_order() -> None:
    people = ids(4)
    values: list[Decimal | None] = [Decimal(4), Decimal(3), Decimal(2), Decimal(1)]
    results = compute_splits(10_000, SplitMode.SHARES, participants(values, people))
    assert [result.user_id for result in results] == people


# --------------------------------------------------------------------- _distribute


@pytest.mark.parametrize(
    ("amount_cents", "weights", "expected"),
    [
        (1_000, [Decimal(1)], [1_000]),
        (1_000, [Decimal(1), Decimal(1), Decimal(1)], [334, 333, 333]),
        (1_000, [Decimal(1), Decimal(0)], [1_000, 0]),
        (100, [Decimal(1), Decimal(2), Decimal(3)], [17, 33, 50]),
        (7, [Decimal(1)] * 7, [1] * 7),
        (1, [Decimal(1)] * 3, [1, 0, 0]),
    ],
)
def test_distribute_totals_and_ordering(
    amount_cents: int, weights: list[Decimal], expected: list[int]
) -> None:
    assert _distribute(amount_cents, weights) == expected
    assert sum(_distribute(amount_cents, weights)) == amount_cents


def test_distribute_is_indifferent_to_weight_scale() -> None:
    small = _distribute(9_999, [Decimal(1), Decimal(2), Decimal(4)])
    large = _distribute(9_999, [Decimal(2_500), Decimal(5_000), Decimal(10_000)])
    assert small == large
    assert sum(small) == 9_999


# ------------------------------------------------------------------- exhaustive run

AMOUNTS: list[int] = [
    *range(1, 1_001),
    9_999,
    123_456,
    1_000_000,
    999_999_999,
    123_456_789_012,
]


def _values_for(mode: SplitMode, amount_cents: int, count: int) -> list[Decimal | None]:
    if mode is SplitMode.EQUAL:
        return [None] * count
    if mode is SplitMode.EXACT:
        base, leftover = divmod(amount_cents, count)
        return [Decimal(base + 1 if index < leftover else base) for index in range(count)]
    if mode is SplitMode.PERCENTAGE:
        return list(even_percentages(count))
    return [Decimal(index + 1) for index in range(count)]


@pytest.mark.parametrize("mode", list(SplitMode))
@pytest.mark.parametrize("count", range(1, 8))
def test_every_mode_always_lands_exactly_on_the_amount(
    mode: SplitMode, count: int
) -> None:
    people = ids(count)
    for amount_cents in AMOUNTS:
        values = _values_for(mode, amount_cents, count)
        results = compute_splits(amount_cents, mode, participants(values, people))
        computed = amounts(results)
        assert len(computed) == count
        assert sum(computed) == amount_cents, (mode, amount_cents, count, computed)
        assert min(computed) >= 0, (mode, amount_cents, count, computed)


@pytest.mark.parametrize("count", range(2, 8))
def test_shares_with_a_single_payer_and_zero_share_riders(count: int) -> None:
    people = ids(count)
    values: list[Decimal | None] = [Decimal(1)] + [Decimal(0)] * (count - 1)
    for amount_cents in (1, 7, 999, 100_000, 123_456_789):
        results = compute_splits(
            amount_cents, SplitMode.SHARES, participants(values, people)
        )
        assert amounts(results) == [amount_cents] + [0] * (count - 1)
