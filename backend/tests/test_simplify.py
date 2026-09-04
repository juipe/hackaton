"""Tests for :mod:`app.services.simplify_service`.

The simplifier is a pure function of the net vector, so these tests build net maps
directly. Every "random" fixture is seeded, and no assertion depends on the clock —
a debt plan that changes between runs is a bug, not a flake.
"""

from __future__ import annotations

import random
import uuid

import pytest

from app.services.balance_service import DebtTransfer, UserBalance
from app.services.simplify_service import simplify, simplify_nets

#: Fixed, ordered ids so tie-breaks (by user id string) are predictable.
USERS = [uuid.UUID(int=index) for index in range(1, 13)]


def _tuples(transfers: list[DebtTransfer]) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    return [
        (transfer.from_user_id, transfer.to_user_id, transfer.amount_cents)
        for transfer in transfers
    ]


def _applied_nets(transfers: list[DebtTransfer]) -> dict[uuid.UUID, int]:
    """The net position each transfer plan produces: received minus sent."""
    nets: dict[uuid.UUID, int] = {}
    for transfer in transfers:
        nets[transfer.from_user_id] = nets.get(transfer.from_user_id, 0) - transfer.amount_cents
        nets[transfer.to_user_id] = nets.get(transfer.to_user_id, 0) + transfer.amount_cents
    return nets


def _assert_plan_is_sound(nets: dict[uuid.UUID, int], transfers: list[DebtTransfer]) -> None:
    applied = _applied_nets(transfers)
    assert all(applied.get(user_id, 0) == net for user_id, net in nets.items())
    assert all(transfer.amount_cents > 0 for transfer in transfers)
    assert all(transfer.from_user_id != transfer.to_user_id for transfer in transfers)
    unsettled = sum(1 for net in nets.values() if net != 0)
    assert len(transfers) <= max(unsettled - 1, 0)
    settled = {user_id for user_id, net in nets.items() if net == 0}
    assert all(
        transfer.from_user_id not in settled and transfer.to_user_id not in settled
        for transfer in transfers
    )


def _random_nets(seed: int, count: int) -> dict[uuid.UUID, int]:
    """A deterministic zero-sum net vector for ``count`` users."""
    rng = random.Random(seed)
    user_ids = USERS[:count]
    values = [rng.randrange(-50_000, 50_001) for _ in user_ids]
    values[-1] -= sum(values)
    return dict(zip(user_ids, values, strict=True))


def test_a_debt_chain_collapses_to_one_transfer() -> None:
    alice, bob, carol = USERS[0], USERS[1], USERS[2]
    # Alice owes Bob 20.00 and Bob owes Carol 20.00: two transfers, one real debt.
    nets = {alice: -2000, bob: 0, carol: 2000}

    transfers = simplify_nets(nets)

    assert _tuples(transfers) == [(alice, carol, 2000)]
    _assert_plan_is_sound(nets, transfers)


def test_simplify_reads_the_nets_off_the_balances() -> None:
    alice, bob, carol = USERS[0], USERS[1], USERS[2]
    balances = [
        UserBalance(user_id=alice, paid_cents=0, owed_cents=2000, net_cents=-2000),
        UserBalance(user_id=bob, paid_cents=2000, owed_cents=2000, net_cents=0),
        UserBalance(user_id=carol, paid_cents=2000, owed_cents=0, net_cents=2000),
    ]

    assert _tuples(simplify(balances)) == [(alice, carol, 2000)]


def test_one_creditor_absorbs_several_debtors() -> None:
    alice, bob, carol = USERS[0], USERS[1], USERS[2]
    nets = {alice: -3000, bob: -2000, carol: 5000}

    transfers = simplify_nets(nets)

    assert _tuples(transfers) == [(alice, carol, 3000), (bob, carol, 2000)]
    _assert_plan_is_sound(nets, transfers)


def test_one_debtor_pays_several_creditors() -> None:
    alice, bob, carol = USERS[0], USERS[1], USERS[2]
    nets = {alice: -7500, bob: 5000, carol: 2500}

    transfers = simplify_nets(nets)

    assert _tuples(transfers) == [(alice, bob, 5000), (alice, carol, 2500)]
    _assert_plan_is_sound(nets, transfers)


def test_a_settled_group_needs_no_transfers() -> None:
    nets = dict.fromkeys(USERS[:4], 0)

    assert simplify_nets(nets) == []
    assert simplify_nets({}) == []
    assert simplify([]) == []


def test_equal_debts_are_broken_by_user_id() -> None:
    first, second, creditor = USERS[0], USERS[1], USERS[2]
    nets = {first: -1000, second: -1000, creditor: 2000}

    forward = simplify_nets(nets)
    reversed_insertion = simplify_nets(
        {creditor: 2000, second: -1000, first: -1000}
    )

    assert _tuples(forward) == [(first, creditor, 1000), (second, creditor, 1000)]
    # Insertion order must not leak into the plan.
    assert _tuples(reversed_insertion) == _tuples(forward)


@pytest.mark.parametrize("seed", range(12))
def test_random_balanced_groups_keep_every_net(seed: int) -> None:
    nets = _random_nets(seed, count=2 + seed % 10)

    transfers = simplify_nets(nets)

    _assert_plan_is_sound(nets, transfers)


@pytest.mark.parametrize("seed", range(6))
def test_simplification_is_repeatable(seed: int) -> None:
    nets = _random_nets(seed, count=8)

    assert _tuples(simplify_nets(nets)) == _tuples(simplify_nets(nets))
    assert _tuples(simplify_nets(dict(reversed(list(nets.items()))))) == _tuples(
        simplify_nets(nets)
    )


def test_the_plan_never_grows_with_the_group() -> None:
    nets = _random_nets(seed=99, count=12)

    transfers = simplify_nets(nets)

    _assert_plan_is_sound(nets, transfers)
    assert len(transfers) <= len(nets) - 1
    assert sum(transfer.amount_cents for transfer in transfers) == sum(
        net for net in nets.values() if net > 0
    )
