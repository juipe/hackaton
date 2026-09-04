"""Money helpers.

Money is stored and transported as **integer minor units** (cents). These helpers
only exist for human-readable output (seed script, logs, tests) and for parsing
user-entered decimal strings. No float ever touches a monetary value.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

#: The service works with the rouble and nothing else (see the contract, §2).
CURRENCY_SYMBOLS: dict[str, str] = {"RUB": "₽"}

DEFAULT_CURRENCY = "RUB"

#: Russian typography: a non-breaking space groups the thousands and separates
#: the amount from the currency sign, which trails the number.
NBSP = " "

_CENTS = Decimal("0.01")


def cents_to_decimal(cents: int) -> Decimal:
    """``1234`` -> ``Decimal('12.34')``."""
    return (Decimal(int(cents)) / Decimal(100)).quantize(_CENTS)


def cents_to_str(cents: int) -> str:
    """``-1234`` -> ``'-12.34'``."""
    return str(cents_to_decimal(cents))


def str_to_cents(value: str | Decimal | int) -> int:
    """Parse a decimal amount into whole cents, rounding half up.

    Raises ``ValueError`` on anything that is not a number.
    """
    if isinstance(value, int):
        return value * 100
    if isinstance(value, Decimal):
        amount = value
    else:
        cleaned = (
            str(value)
            .strip()
            .replace("₽", "")
            .replace(NBSP, "")
            .replace(" ", "")
            .replace(",", ".")
        )
        if not cleaned:
            raise ValueError("Укажите сумму")
        try:
            amount = Decimal(cleaned)
        except InvalidOperation as exc:  # pragma: no cover - defensive
            raise ValueError("Сумма должна быть числом") from exc
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _group_thousands(digits: str) -> str:
    """``1234567`` -> ``1 234 567`` (non-breaking spaces)."""
    parts: list[str] = []
    while len(digits) > 3:
        parts.append(digits[-3:])
        digits = digits[:-3]
    parts.append(digits)
    return NBSP.join(reversed(parts))


def format_money(cents: int, currency: str = DEFAULT_CURRENCY) -> str:
    """``123456`` -> ``'1 234,56 ₽'``; negatives render as ``-1 234,56 ₽``."""
    symbol = CURRENCY_SYMBOLS.get((currency or "").upper(), CURRENCY_SYMBOLS[DEFAULT_CURRENCY])
    whole, _, fraction = str(cents_to_decimal(abs(int(cents)))).partition(".")
    sign = "-" if cents < 0 else ""
    return f"{sign}{_group_thousands(whole)},{fraction or '00'}{NBSP}{symbol}"


def format_signed(cents: int, currency: str = DEFAULT_CURRENCY) -> str:
    """Like :func:`format_money` but always shows a leading ``+`` for credits."""
    if cents > 0:
        return f"+{format_money(cents, currency)}"
    return format_money(cents, currency)


__all__ = [
    "CURRENCY_SYMBOLS",
    "DEFAULT_CURRENCY",
    "NBSP",
    "cents_to_decimal",
    "cents_to_str",
    "format_money",
    "format_signed",
    "str_to_cents",
]
