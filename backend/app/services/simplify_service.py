"""Debt simplification.

The pairwise graph is honest but noisy: in a group of five, "everybody owes whoever
happened to pay" easily means eight transfers for four real debts. Simplification
replaces it with a small set of payments that leaves every net position untouched.

Only the net vector matters — who owes whom pairwise is irrelevant to the result,
which is why simplification provably cannot change anyone's balance. The algorithm
repeatedly matches the largest debtor against the largest creditor; each match
settles at least one of the two, so the plan holds at most ``n - 1`` transfers for
``n`` participants. Ties are broken by user id string, so identical input always
yields identical output — a recommendation that reshuffled between page loads would
be useless.
"""

from __future__ import annotations

import heapq
import uuid

from app.services.balance_service import DebtTransfer, UserBalance

#: Heap entry: (signed remaining cents, user id string, user id). The signed amount
#: is negative on both heaps — a debtor's net is already negative and a creditor's
#: net is negated — so the smallest element is always the largest position, and the
#: id string next to it makes the ordering total.
_HeapEntry = tuple[int, str, uuid.UUID]


def simplify(balances: list[UserBalance]) -> list[DebtTransfer]:
    """Minimised transfers for a group's balance list."""
    return simplify_nets({balance.user_id: balance.net_cents for balance in balances})


def simplify_nets(nets: dict[uuid.UUID, int]) -> list[DebtTransfer]:
    """Minimised transfers for a ``{user_id: net_cents}`` map.

    A positive net means the group owes that user. Users with a zero net are left
    out: they are settled already and must not appear in the plan. Nets are expected
    to sum to zero (:func:`app.services.balance_service.compute_group_balances`
    guarantees it); with an unbalanced map the matching simply stops when one side
    runs out.
    """
    debtors: list[_HeapEntry] = [
        (net, str(user_id), user_id) for user_id, net in nets.items() if net < 0
    ]
    creditors: list[_HeapEntry] = [
        (-net, str(user_id), user_id) for user_id, net in nets.items() if net > 0
    ]
    heapq.heapify(debtors)
    heapq.heapify(creditors)

    transfers: list[DebtTransfer] = []
    while debtors and creditors:
        debt, debtor_key, debtor_id = heapq.heappop(debtors)
        credit, creditor_key, creditor_id = heapq.heappop(creditors)
        amount_cents = min(-debt, -credit)
        transfers.append(
            DebtTransfer(
                from_user_id=debtor_id,
                to_user_id=creditor_id,
                amount_cents=amount_cents,
            )
        )
        if debt + amount_cents < 0:
            heapq.heappush(debtors, (debt + amount_cents, debtor_key, debtor_id))
        if credit + amount_cents < 0:
            heapq.heappush(creditors, (credit + amount_cents, creditor_key, creditor_id))

    return transfers


__all__ = ["simplify", "simplify_nets"]
