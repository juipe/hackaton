"""Database bootstrap and demo data.

``ensure_categories`` is idempotent and runs on every startup, so a fresh database
always has the category set the UI expects. ``seed_demo_data`` builds the reviewable
demo world (users, groups, expenses across all four split modes, payments).
"""

from __future__ import annotations

import logging
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_invite_token, hash_invite_token, hash_password
from app.models.activity import ActivityType
from app.models.category import DEFAULT_CATEGORIES, Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.invite import GroupInvite
from app.models.member import GroupMember, GroupRole
from app.models.payment import Payment
from app.models.user import User
from app.repositories import category_repo, user_repo
from app.services.activity_service import log_activity
from app.services.notification_service import build_invite_url, get_notification_service
from app.utils.time import utcnow

logger = logging.getLogger("skladchina.seed")


def ensure_categories(db: Session) -> list[Category]:
    """Create any missing categories and align names, icons and ordering.

    Idempotent: safe to call on every application startup.
    """
    existing = {category.slug: category for category in category_repo.list_all(db)}
    result: list[Category] = []
    for index, (slug, name, icon) in enumerate(DEFAULT_CATEGORIES, start=1):
        category = existing.get(slug)
        if category is None:
            category = Category(slug=slug, name=name, icon=icon, sort_order=index)
            db.add(category)
        else:
            category.name = name
            category.icon = icon
            category.sort_order = index
        result.append(category)
    db.flush()
    return result


# --------------------------------------------------------------------------- #
# Demo world specification
# --------------------------------------------------------------------------- #

DEMO_PASSWORD = "Demo1234!"

#: Fixed so two seeds of the same world produce the same timestamps.
_RANDOM_SEED = 20240514

_OLYA = "olya"
_SASHA = "sasha"
_KOSTYA = "kostya"
_MAKSIM = "maksim"
_ZHORA = "zhora"

_FLAT = "Квартира на Вайнера"
_HACK = "Хакатон Сбера"
_RAFT = "Сплав по Чусовой"


@dataclass(frozen=True)
class _UserSpec:
    key: str
    name: str
    email: str


@dataclass(frozen=True)
class _GroupSpec:
    name: str
    currency: str
    description: str
    owner: str
    members: tuple[str, ...]
    created_days_ago: int


@dataclass(frozen=True)
class _Split:
    mode: SplitMode
    participants: tuple[tuple[str, Decimal | None], ...]


@dataclass(frozen=True)
class _ExpenseSpec:
    group: str
    days_ago: int
    title: str
    category: str
    amount_cents: int
    paid_by: str
    split: _Split
    entered_by: str | None = None


@dataclass(frozen=True)
class _PaymentSpec:
    group: str
    days_ago: int
    from_user: str
    to_user: str
    amount_cents: int
    note: str


@dataclass(frozen=True)
class _InviteSpec:
    group: str
    inviter: str
    invited_email: str


def _equal(*keys: str) -> _Split:
    return _Split(SplitMode.EQUAL, tuple((key, None) for key in keys))


def _exact(**cents: int) -> _Split:
    """Exact shares, in cents, keyed by user. Must add up to the expense amount."""
    return _Split(SplitMode.EXACT, tuple((key, Decimal(value)) for key, value in cents.items()))


def _percent(**percent: str) -> _Split:
    """Percentage shares keyed by user. Must add up to 100."""
    return _Split(
        SplitMode.PERCENTAGE, tuple((key, Decimal(value)) for key, value in percent.items())
    )


def _shares(**shares: int) -> _Split:
    """Weighted shares keyed by user, e.g. a double room counting for two."""
    return _Split(SplitMode.SHARES, tuple((key, Decimal(value)) for key, value in shares.items()))


DEMO_USERS: tuple[_UserSpec, ...] = (
    _UserSpec(_OLYA, "Оля", "olya@skladchina.ru"),
    _UserSpec(_SASHA, "Саша", "sasha@skladchina.ru"),
    _UserSpec(_KOSTYA, "Костя", "kostya@skladchina.ru"),
    _UserSpec(_MAKSIM, "Максим", "maksim@skladchina.ru"),
    _UserSpec(_ZHORA, "Жора", "zhora@skladchina.ru"),
)

DEMO_EMAILS: tuple[str, ...] = tuple(spec.email for spec in DEMO_USERS)

DEMO_GROUPS: tuple[_GroupSpec, ...] = (
    _GroupSpec(
        _FLAT,
        "RUB",
        "Аренда, ЖКХ и всё, что делим на троих.",
        _SASHA,
        (_KOSTYA, _MAKSIM),
        185,
    ),
    _GroupSpec(
        _RAFT,
        "RUB",
        "Четыре дня на реке: катамараны, продукты и баня.",
        _MAKSIM,
        (_OLYA, _SASHA, _KOSTYA, _ZHORA),
        96,
    ),
    _GroupSpec(
        _HACK,
        "RUB",
        "Расходы команды на хакатоне: кофе, коворкинг, пицца.",
        _OLYA,
        (_SASHA, _KOSTYA, _MAKSIM),
        21,
    ),
)

DEMO_GROUP_NAMES: tuple[str, ...] = tuple(spec.name for spec in DEMO_GROUPS)

#: Everyone who belongs to each group, owner first — the source of truth the
#: expense and payment tables below are validated against.
_GROUP_MEMBER_KEYS: dict[str, tuple[str, ...]] = {
    spec.name: (spec.owner, *spec.members) for spec in DEMO_GROUPS
}

#: Fields in order: group, days ago, title, category slug, amount in cents, payer, split.
#: Amounts are kopecks: 60 000 ₽ is 6_000_000.
DEMO_EXPENSES: tuple[_ExpenseSpec, ...] = (
    # Квартира на Вайнера — аренда по фиксированному ключу и общий быт.
    _ExpenseSpec(_FLAT, 176, "Аренда квартиры", "rent", 6_000_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 172, "ЖКХ", "utilities", 742_000, _SASHA,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 168, "Пятёрочка", "groceries", 364_000, _KOSTYA,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 146, "Аренда квартиры", "rent", 6_000_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 142, "ЖКХ", "utilities", 689_000, _KOSTYA,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 138, "Мегамарт", "groceries", 428_000, _MAKSIM,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 131, "Ресторан «Паштет»", "food", 540_000, _SASHA,
                 _exact(sasha=210_000, kostya=180_000, maksim=150_000)),
    _ExpenseSpec(_FLAT, 116, "Аренда квартиры", "rent", 6_000_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 112, "Интернет и ТВ", "subscriptions", 85_000, _MAKSIM,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 104, "Аптека «Живика»", "health", 186_000, _KOSTYA,
                 _exact(kostya=112_000, maksim=74_000)),
    _ExpenseSpec(_FLAT, 86, "Аренда квартиры", "rent", 6_200_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 74, "Пятёрочка", "groceries", 398_000, _MAKSIM,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 62, "Хофф — стеллаж", "shopping", 1_290_000, _KOSTYA,
                 _shares(sasha=2, kostya=1, maksim=1), entered_by=_SASHA),
    _ExpenseSpec(_FLAT, 56, "Аренда квартиры", "rent", 6_200_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 41, "Кинотеатр «Салют»", "entertainment", 195_000, _MAKSIM,
                 _shares(sasha=1, kostya=1, maksim=1)),
    _ExpenseSpec(_FLAT, 26, "Аренда квартиры", "rent", 6_200_000, _SASHA,
                 _percent(sasha="40", kostya="35", maksim="25")),
    _ExpenseSpec(_FLAT, 22, "ЖКХ", "utilities", 815_000, _KOSTYA,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 12, "Мегамарт", "groceries", 452_000, _SASHA,
                 _equal(_SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_FLAT, 4, "Яндекс Такси", "transport", 52_000, _MAKSIM,
                 _equal(_SASHA, _MAKSIM)),

    # Сплав по Чусовой — четыре дня на воде, платит в основном Максим.
    _ExpenseSpec(_RAFT, 92, "Аренда катамаранов", "travel", 1_600_000, _MAKSIM,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM, _ZHORA)),
    _ExpenseSpec(_RAFT, 91, "Трансфер до Слободы", "transport", 650_000, _MAKSIM,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM, _ZHORA)),
    _ExpenseSpec(_RAFT, 91, "Продукты на сплав", "groceries", 940_000, _OLYA,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM, _ZHORA)),
    _ExpenseSpec(_RAFT, 90, "Бензин", "transport", 480_000, _MAKSIM,
                 _percent(olya="10", sasha="25", kostya="15", maksim="40", zhora="10")),
    _ExpenseSpec(_RAFT, 89, "Шашлык и мангал", "food", 520_000, _SASHA,
                 _exact(olya=100_000, sasha=110_000, kostya=110_000, maksim=110_000,
                        zhora=90_000)),
    _ExpenseSpec(_RAFT, 88, "Спальники и снаряжение", "shopping", 1_120_000, _MAKSIM,
                 _shares(olya=1, sasha=1, kostya=1, maksim=2, zhora=2), entered_by=_OLYA),
    _ExpenseSpec(_RAFT, 87, "Баня в Каменке", "entertainment", 750_000, _KOSTYA,
                 _shares(olya=1, sasha=1, kostya=1, maksim=1, zhora=2)),
    _ExpenseSpec(_RAFT, 86, "Сувениры из Чусового", "shopping", 330_000, _OLYA,
                 _exact(olya=90_000, sasha=60_000, kostya=60_000, maksim=60_000,
                        zhora=60_000)),

    # Хакатон Сбера — три дня, четыре человека и много кофе.
    _ExpenseSpec(_HACK, 20, "Коворкинг «Соль»", "housing", 880_000, _OLYA,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_HACK, 20, "Домен и хостинг", "subscriptions", 149_000, _OLYA,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_HACK, 19, "Такси до Сбер-центра", "transport", 48_000, _MAKSIM,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_HACK, 19, "Кофе в «Симпл»", "food", 132_000, _KOSTYA,
                 _exact(olya=32_000, sasha=36_000, kostya=34_000, maksim=30_000)),
    _ExpenseSpec(_HACK, 18, "Пицца на команду", "food", 264_000, _SASHA,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_HACK, 17, "Обед в «Вилке-Ложке»", "food", 236_000, _SASHA,
                 _equal(_OLYA, _SASHA, _KOSTYA, _MAKSIM)),
    _ExpenseSpec(_HACK, 17, "Энергетики и снеки", "groceries", 178_000, _KOSTYA,
                 _exact(olya=38_000, sasha=52_000, kostya=46_000, maksim=42_000)),
    _ExpenseSpec(_HACK, 16, "Ужин после защиты", "food", 300_000, _MAKSIM,
                 _shares(olya=1, sasha=2, kostya=1, maksim=1)),
    _ExpenseSpec(_HACK, 16, "Печать постера", "other", 120_000, _OLYA,
                 _percent(olya="40", sasha="20", kostya="20", maksim="20"),
                 entered_by=_SASHA),
)

#: Partial settle-ups: enough to look lived-in, never enough to zero a group out.
DEMO_PAYMENTS: tuple[_PaymentSpec, ...] = (
    _PaymentSpec(_FLAT, 40, _KOSTYA, _SASHA, 3_500_000, "Моя доля за аренду"),
    _PaymentSpec(_FLAT, 18, _MAKSIM, _SASHA, 2_400_000, "Догоняю по ЖКХ"),
    _PaymentSpec(_RAFT, 70, _SASHA, _MAKSIM, 500_000, "За катамараны"),
    _PaymentSpec(_RAFT, 62, _ZHORA, _OLYA, 300_000, "Половина за продукты"),
    _PaymentSpec(_RAFT, 55, _KOSTYA, _MAKSIM, 350_000, "За бензин и трансфер"),
    _PaymentSpec(_HACK, 12, _SASHA, _OLYA, 180_000, "Кофе и такси"),
    _PaymentSpec(_HACK, 9, _KOSTYA, _OLYA, 150_000, "За коворкинг"),
)

#: Жора — демо-аккаунт, но в «Хакатон Сбера» он не входит: ревьюер может войти
#: под ним и принять это приглашение вживую.
DEMO_INVITE = _InviteSpec(_HACK, _OLYA, "zhora@skladchina.ru")


# --------------------------------------------------------------------------- #
# Demo world builder
# --------------------------------------------------------------------------- #


def seed_demo_data(db: Session, *, reset: bool = False) -> None:
    """Create the demo users, groups, expenses, payments and pending invite.

    Idempotent: a second call is a no-op unless ``reset`` is set, in which case the
    demo users and their groups are deleted and rebuilt. Never commits — the caller
    owns the transaction.
    """
    first = DEMO_USERS[0]
    existing = user_repo.get_by_email(db, first.email)
    if existing is not None and not reset:
        logger.info("Demo data already seeded (%s exists), nothing to do.", first.email)
        return
    if existing is not None:
        logger.info("Resetting demo data.")
        _delete_demo_world(db)

    _validate_specs()

    rng = random.Random(_RANDOM_SEED)
    categories = {category.slug: category for category in ensure_categories(db)}
    users = _create_users(db)
    groups = _create_groups(db, users)
    expenses = [
        _create_expense(db, spec, users=users, groups=groups, categories=categories, rng=rng)
        for spec in DEMO_EXPENSES
    ]
    payments = _create_payments(db, users=users, groups=groups, rng=rng)
    _create_invite(db, users=users, groups=groups)
    db.flush()

    _assert_invariants(db, groups=groups, expenses=expenses)
    logger.info(
        "Seeded demo data: %d users, %d groups, %d expenses, %d payments, 1 pending invite.",
        len(users),
        len(groups),
        len(expenses),
        len(payments),
    )


def _validate_specs() -> None:
    """Fail fast on a typo in the tables above, before anything is written."""
    known_slugs = {slug for slug, _name, _icon in DEFAULT_CATEGORIES}
    known_keys = {spec.key for spec in DEMO_USERS}
    for spec in DEMO_EXPENSES:
        members = _GROUP_MEMBER_KEYS[spec.group]
        keys = [key for key, _value in spec.split.participants]
        if spec.category not in known_slugs:
            raise RuntimeError(
                f"Demo expense {spec.title!r} uses unknown category {spec.category!r}"
            )
        if spec.amount_cents <= 0:
            raise RuntimeError(f"Demo expense {spec.title!r} must have a positive amount")
        if spec.paid_by not in keys:
            raise RuntimeError(f"Demo expense {spec.title!r}: the payer is not a participant")
        outsiders = sorted(set(keys) - set(members))
        if outsiders:
            raise RuntimeError(
                f"Demo expense {spec.title!r}: {outsiders} are not in {spec.group!r}"
            )
        if spec.entered_by is not None and spec.entered_by not in members:
            raise RuntimeError(
                f"Demo expense {spec.title!r}: {spec.entered_by!r} is not in {spec.group!r}"
            )
    for payment in DEMO_PAYMENTS:
        members = _GROUP_MEMBER_KEYS[payment.group]
        if payment.from_user not in members or payment.to_user not in members:
            raise RuntimeError(f"Demo payment in {payment.group!r} involves a non-member")
        if payment.from_user == payment.to_user:
            raise RuntimeError(f"Demo payment in {payment.group!r} needs two different people")
    invited_group_emails = {
        spec.email for spec in DEMO_USERS if spec.key in _GROUP_MEMBER_KEYS[DEMO_INVITE.group]
    }
    if DEMO_INVITE.invited_email in invited_group_emails:
        raise RuntimeError(f"Demo invite target is already in {DEMO_INVITE.group!r}")
    unknown_split_keys = {
        key
        for spec in DEMO_EXPENSES
        for key, _value in spec.split.participants
        if key not in known_keys
    }
    if unknown_split_keys:
        raise RuntimeError(f"Demo expenses reference unknown users: {sorted(unknown_split_keys)}")


def _delete_demo_world(db: Session) -> None:
    """Remove the demo users and every group they belong to.

    Groups go first: expenses and payments reference users with ``ON DELETE
    RESTRICT``, and dropping the group is what cascades them away.
    """
    users = [
        user
        for user in (user_repo.get_by_email(db, email) for email in DEMO_EMAILS)
        if user is not None
    ]
    if not users:
        return
    user_ids = [user.id for user in users]
    group_ids = set(
        db.scalars(select(GroupMember.group_id).where(GroupMember.user_id.in_(user_ids)))
    )
    group_ids.update(db.scalars(select(Group.id).where(Group.owner_id.in_(user_ids))))
    if group_ids:
        for group in db.scalars(select(Group).where(Group.id.in_(group_ids))):
            db.delete(group)
        db.flush()
    for user in users:
        db.delete(user)
    db.flush()


def _create_users(db: Session) -> dict[str, User]:
    # One bcrypt round for all five accounts: they share the demo password and
    # hashing is deliberately slow.
    password_hash = hash_password(DEMO_PASSWORD)
    created: dict[str, User] = {}
    for index, spec in enumerate(DEMO_USERS):
        registered_at = utcnow() - timedelta(days=190 - index)
        user = User(
            name=spec.name,
            email=spec.email,
            password_hash=password_hash,
            created_at=registered_at,
            updated_at=registered_at,
        )
        db.add(user)
        created[spec.key] = user
    db.flush()
    return created


def _create_groups(db: Session, users: dict[str, User]) -> dict[str, Group]:
    created: dict[str, Group] = {}
    for spec in DEMO_GROUPS:
        owner = users[spec.owner]
        created_at = utcnow() - timedelta(days=spec.created_days_ago)
        group = Group(
            name=spec.name,
            description=spec.description,
            owner_id=owner.id,
            currency=spec.currency,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(group)
        db.flush()
        db.add(
            GroupMember(
                group_id=group.id,
                user_id=owner.id,
                role=GroupRole.OWNER.value,
                joined_at=created_at,
            )
        )
        _log(
            db,
            group_id=group.id,
            actor_id=owner.id,
            type=ActivityType.GROUP_CREATED,
            entity_id=group.id,
            meta={"name": group.name, "currency": group.currency},
            when=created_at,
        )
        for index, key in enumerate(spec.members, start=1):
            member = users[key]
            joined_at = created_at + timedelta(hours=4 * index)
            db.add(
                GroupMember(
                    group_id=group.id,
                    user_id=member.id,
                    role=GroupRole.MEMBER.value,
                    joined_at=joined_at,
                )
            )
            _log(
                db,
                group_id=group.id,
                actor_id=member.id,
                type=ActivityType.MEMBER_JOINED,
                entity_id=member.id,
                meta={"name": member.name},
                when=joined_at,
            )
        db.flush()
        created[spec.name] = group
    return created


def _create_expense(
    db: Session,
    spec: _ExpenseSpec,
    *,
    users: dict[str, User],
    groups: dict[str, Group],
    categories: dict[str, Category],
    rng: random.Random,
) -> Expense:
    # Deferred import: ``app.main`` imports this module at start-up for
    # :func:`ensure_categories`, which has no business pulling in the split engine.
    from app.services.split_engine import SplitInput, compute_splits

    group = groups[spec.group]
    payer = users[spec.paid_by]
    creator = users[spec.entered_by] if spec.entered_by is not None else payer
    category = categories[spec.category]

    occurred_at = utcnow() - timedelta(
        days=spec.days_ago, hours=rng.randrange(12), minutes=rng.randrange(60)
    )
    # Expenses are typed into the app a little after they happen.
    entered_at = occurred_at + timedelta(minutes=rng.randrange(5, 240))

    results = compute_splits(
        spec.amount_cents,
        spec.split.mode,
        [
            SplitInput(user_id=users[key].id, value=value)
            for key, value in spec.split.participants
        ],
    )
    expense = Expense(
        group_id=group.id,
        created_by=creator.id,
        title=spec.title,
        amount_cents=spec.amount_cents,
        currency=group.currency,
        category_id=category.id,
        paid_by=payer.id,
        split_mode=spec.split.mode.value,
        occurred_at=occurred_at,
        created_at=entered_at,
        updated_at=entered_at,
    )
    expense.splits = [
        ExpenseSplit(
            user_id=result.user_id,
            split_mode=spec.split.mode.value,
            input_value=result.input_value,
            calculated_amount_cents=result.calculated_amount_cents,
        )
        for result in results
    ]
    db.add(expense)
    db.flush()
    _log(
        db,
        group_id=group.id,
        actor_id=creator.id,
        type=ActivityType.EXPENSE_CREATED,
        entity_id=expense.id,
        meta={
            "title": expense.title,
            "amount_cents": expense.amount_cents,
            "currency": expense.currency,
            "category": category.slug,
        },
        when=entered_at,
    )
    return expense


def _create_payments(
    db: Session,
    *,
    users: dict[str, User],
    groups: dict[str, Group],
    rng: random.Random,
) -> list[Payment]:
    created: list[Payment] = []
    for spec in DEMO_PAYMENTS:
        group = groups[spec.group]
        sender = users[spec.from_user]
        recipient = users[spec.to_user]
        paid_at = utcnow() - timedelta(days=spec.days_ago, hours=rng.randrange(12))
        payment = Payment(
            group_id=group.id,
            from_user_id=sender.id,
            to_user_id=recipient.id,
            amount_cents=spec.amount_cents,
            currency=group.currency,
            note=spec.note,
            paid_at=paid_at,
            created_at=paid_at,
        )
        db.add(payment)
        db.flush()
        _log(
            db,
            group_id=group.id,
            actor_id=sender.id,
            type=ActivityType.PAYMENT_CREATED,
            entity_id=payment.id,
            meta={
                "amount_cents": payment.amount_cents,
                "currency": payment.currency,
                "from_name": sender.name,
                "to_name": recipient.name,
            },
            when=paid_at,
        )
        created.append(payment)
    return created


def _create_invite(
    db: Session, *, users: dict[str, User], groups: dict[str, Group]
) -> GroupInvite:
    group = groups[DEMO_INVITE.group]
    inviter = users[DEMO_INVITE.inviter]
    created_at = utcnow() - timedelta(days=2, hours=4)
    token = generate_invite_token()
    invite = GroupInvite(
        group_id=group.id,
        inviter_id=inviter.id,
        invited_email=DEMO_INVITE.invited_email,
        token_hash=hash_invite_token(token),
        expires_at=utcnow() + timedelta(hours=settings.invite_expire_hours),
        created_at=created_at,
    )
    db.add(invite)
    db.flush()
    _log(
        db,
        group_id=group.id,
        actor_id=inviter.id,
        type=ActivityType.INVITE_CREATED,
        entity_id=invite.id,
        meta={"invited_email": invite.invited_email},
        when=created_at,
    )
    # Only the hash is persisted, so the usable link has to be surfaced now or never.
    get_notification_service().send_group_invite(
        to_email=invite.invited_email,
        group_name=group.name,
        inviter_name=inviter.name,
        invite_url=build_invite_url(token),
    )
    return invite


def _log(
    db: Session,
    *,
    group_id: uuid.UUID,
    actor_id: uuid.UUID,
    type: ActivityType,
    entity_id: uuid.UUID,
    meta: dict[str, Any],
    when: datetime,
) -> None:
    activity = log_activity(
        db,
        group_id=group_id,
        actor_id=actor_id,
        type=type,
        entity_id=entity_id,
        meta=meta,
    )
    # log_activity stamps "now"; a seeded feed has to read as a timeline instead.
    activity.created_at = when
    db.flush()


def _group_nets(db: Session, group_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Paid minus owed per user, following the ledger rules of the balance engine."""
    nets: dict[uuid.UUID, int] = defaultdict(int)
    expenses = db.scalars(
        select(Expense).where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
    )
    for expense in expenses:
        nets[expense.paid_by] += expense.amount_cents
        for split in expense.splits:
            nets[split.user_id] -= split.calculated_amount_cents
    payments = db.scalars(select(Payment).where(Payment.group_id == group_id))
    for payment in payments:
        nets[payment.from_user_id] += payment.amount_cents
        nets[payment.to_user_id] -= payment.amount_cents
    return dict(nets)


def _assert_invariants(
    db: Session, *, groups: dict[str, Group], expenses: list[Expense]
) -> None:
    """Refuse to hand over a demo world that does not add up."""
    for expense in expenses:
        total = sum(split.calculated_amount_cents for split in expense.splits)
        if total != expense.amount_cents:
            raise RuntimeError(
                f"Seeded expense {expense.title!r} splits to {total}, "
                f"expected {expense.amount_cents}"
            )
    for group in groups.values():
        nets = _group_nets(db, group.id)
        if sum(nets.values()) != 0:
            raise RuntimeError(f"Seeded group {group.name!r} does not balance: {nets}")
        if sum(1 for net in nets.values() if net != 0) < 2:
            raise RuntimeError(f"Seeded group {group.name!r} has no outstanding balances to show")


__all__ = [
    "DEMO_EMAILS",
    "DEMO_EXPENSES",
    "DEMO_GROUPS",
    "DEMO_GROUP_NAMES",
    "DEMO_INVITE",
    "DEMO_PASSWORD",
    "DEMO_PAYMENTS",
    "DEMO_USERS",
    "ensure_categories",
    "seed_demo_data",
]
