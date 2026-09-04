"""Voice-to-expense-draft orchestration.

Turns a recorded voice note into an ephemeral, validated expense draft: local
Whisper transcription -> local Qwen extraction (via Ollama) -> resolution of
payer, participants and category against the group's real members and
categories, plus validation of whatever split Qwen thought it heard. This
module never writes to the database and never creates an expense — that only
happens once the user confirms the draft through the existing expense
creation flow (``expense_service.create_expense``).

Split-total validation here never blocks the request — it only adds a
``warnings`` entry. The actual safety net is the same one manual entry
already has: ``ExpenseForm`` (via ``split_engine`` on submit) refuses to save
an exact/percentage/shares split that doesn't add up, so a voice draft that
got a number wrong is caught by the exact same, already-tested code path
manual entry uses — never silently persisted, whether or not this module's
own check happens to catch it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.models.category import Category
from app.models.expense import SplitMode
from app.models.group import Group
from app.models.member import GroupMember
from app.models.user import User
from app.repositories import category_repo, group_repo
from app.schemas.category import CategoryOut
from app.schemas.member import MemberOut
from app.schemas.voice import (
    AmbiguousParticipant,
    FieldResolution,
    LLMExpenseExtraction,
    LLMParticipantShare,
    ParticipantsResolution,
    ResolvedParticipant,
    VoiceExpenseDraftOut,
)
from app.services import ollama_service, whisper_service
from app.utils.money import str_to_cents

#: Words a speaker uses to refer to themself instead of naming who paid.
_SELF_WORDS = {"я", "мне", "меня", "сам", "сама", "себя", "мной", "самим", "самой"}

_SPLIT_MODES_BY_VALUE = {mode.value: mode for mode in SplitMode}


def build_draft(
    db: Session, *, group: Group, actor: User, audio_bytes: bytes
) -> VoiceExpenseDraftOut:
    warnings: list[str] = []

    try:
        transcript = whisper_service.transcribe(audio_bytes).strip()
    except Exception as exc:  # pragma: no cover - depends on audio codec support
        raise BadRequest("Не удалось обработать аудиозапись") from exc
    if not transcript:
        raise BadRequest("Не удалось распознать речь в записи")

    members = group_repo.list_members(db, group.id)
    categories = category_repo.list_all(db)

    try:
        extraction = ollama_service.extract_expense(transcript, categories)
        ollama_succeeded = True
    except ollama_service.OllamaError:
        warnings.append(
            "Не удалось получить структурированные данные от локальной модели Qwen"
        )
        extraction = LLMExpenseExtraction()
        ollama_succeeded = False

    split_mode = _resolve_split_mode(extraction.split_mode)
    participants = _resolve_participants(extraction.participants, members, actor)

    amount_cents = _resolve_amount(extraction.amount, warnings)
    if amount_cents is None and split_mode == SplitMode.EXACT:
        # "Саша 500, Максим 1000, я 1500" never states a total — it's the sum
        # of the stated shares, not a guess, so this is safe to derive even
        # though the rule elsewhere is never to invent a number.
        amount_cents = _infer_amount_from_exact_shares(participants)

    _validate_split(split_mode, amount_cents, participants.resolved, warnings)

    return VoiceExpenseDraftOut(
        transcript=transcript,
        title=(extraction.title or "").strip() or None,
        description=(extraction.description or "").strip() or None,
        amount_cents=amount_cents,
        occurred_at=_resolve_date(extraction.occurred_at, warnings),
        split_mode=split_mode,
        payer=_resolve_payer(extraction.payer_name, members, actor),
        participants=participants,
        category=_resolve_category(extraction.category_slug, categories, ollama_succeeded),
        warnings=warnings,
    )


def _resolve_split_mode(raw: str | None) -> SplitMode:
    if raw:
        mode = _SPLIT_MODES_BY_VALUE.get(raw.strip().casefold())
        if mode is not None:
            return mode
    return SplitMode.EQUAL


def _resolve_amount(raw: str | None, warnings: list[str]) -> int | None:
    if not raw or not raw.strip():
        return None
    try:
        return str_to_cents(raw)
    except ValueError:
        warnings.append("Не удалось распознать сумму")
        return None


def _resolve_date(raw: str | None, warnings: list[str]) -> datetime | None:
    if not raw or not raw.strip():
        return None
    try:
        parsed_date = date.fromisoformat(raw.strip())
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
    except ValueError:
        warnings.append("Не удалось распознать дату")
        return None


def _parse_decimal(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    cleaned = raw.strip().replace(",", ".").replace("%", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _match_members(raw: str, members: list[GroupMember]) -> list[GroupMember]:
    needle = raw.strip().casefold()
    if not needle:
        return []
    exact = [m for m in members if m.user.name.strip().casefold() == needle]
    if exact:
        return exact
    return [
        m
        for m in members
        if needle in m.user.name.casefold() or m.user.name.strip().casefold().split()[0] == needle
    ]


def _resolve_payer(
    raw_name: str | None, members: list[GroupMember], actor: User
) -> FieldResolution[MemberOut]:
    raw = (raw_name or "").strip()
    if not raw or raw.casefold() in _SELF_WORDS:
        actor_member = next((m for m in members if m.user_id == actor.id), None)
        if actor_member is not None:
            return FieldResolution[MemberOut](
                status="resolved", value=MemberOut.model_validate(actor_member)
            )

    matches = _match_members(raw, members)
    if len(matches) == 1:
        return FieldResolution[MemberOut](
            status="resolved", value=MemberOut.model_validate(matches[0])
        )
    if matches:
        return FieldResolution[MemberOut](
            status="ambiguous",
            candidates=[MemberOut.model_validate(m) for m in matches],
            raw_text=raw or None,
        )
    return FieldResolution[MemberOut](status="unresolved", raw_text=raw or None)


def _resolve_participants(
    items: list[LLMParticipantShare], members: list[GroupMember], actor: User
) -> ParticipantsResolution:
    resolved: list[ResolvedParticipant] = []
    resolved_ids: set = set()
    ambiguous: list[AmbiguousParticipant] = []
    unresolved: list[str] = []

    for item in items:
        raw = item.name.strip()
        if not raw:
            continue
        value = (item.value or "").strip() or None

        if raw.casefold() in _SELF_WORDS:
            actor_member = next((m for m in members if m.user_id == actor.id), None)
            matches = [actor_member] if actor_member is not None else []
        else:
            matches = _match_members(raw, members)

        if len(matches) == 1:
            member = matches[0]
            if member.id not in resolved_ids:
                resolved.append(
                    ResolvedParticipant(member=MemberOut.model_validate(member), value=value)
                )
                resolved_ids.add(member.id)
        elif matches:
            ambiguous.append(
                AmbiguousParticipant(
                    raw_text=raw, candidates=[MemberOut.model_validate(m) for m in matches]
                )
            )
        else:
            unresolved.append(raw)

    return ParticipantsResolution(resolved=resolved, ambiguous=ambiguous, unresolved=unresolved)


def _resolve_category(
    raw_slug: str | None, categories: list[Category], ollama_succeeded: bool
) -> FieldResolution[CategoryOut]:
    """Qwen picks a category by slug from the real list — see the prompt in
    ``ollama_service``. A slug that matches resolves directly; the model is
    instructed to fall back to "other" itself when nothing fits, so an
    unmatched slug here means it slipped up, not that the transcript was
    unclear — falling back to "other" on our side too keeps that promise
    ("only unresolved on a genuine failure") even then.

    When Qwen never ran at all (``ollama_succeeded`` is False), there is no
    semantic judgement to fall back on, so the category stays unresolved —
    that is the genuine technical/data problem this status is for.
    """
    slug = (raw_slug or "").strip().casefold()
    match = next((c for c in categories if c.slug.casefold() == slug), None) if slug else None
    if match is not None:
        return FieldResolution[CategoryOut](
            status="resolved", value=CategoryOut.model_validate(match)
        )

    if ollama_succeeded:
        fallback = next((c for c in categories if c.slug.casefold() == "other"), None)
        if fallback is not None:
            return FieldResolution[CategoryOut](
                status="resolved", value=CategoryOut.model_validate(fallback)
            )

    return FieldResolution[CategoryOut](status="unresolved", raw_text=raw_slug or None)


def _infer_amount_from_exact_shares(participants: ParticipantsResolution) -> int | None:
    if participants.ambiguous or participants.unresolved or not participants.resolved:
        return None
    try:
        cents = [str_to_cents(rp.value) for rp in participants.resolved if rp.value is not None]
    except ValueError:
        return None
    if len(cents) != len(participants.resolved):
        return None
    return sum(cents)


def _validate_split(
    split_mode: SplitMode,
    amount_cents: int | None,
    resolved: list[ResolvedParticipant],
    warnings: list[str],
) -> None:
    """Never corrects anything — only tells the user, via ``warnings``, that
    the numbers Qwen heard don't add up, so they know to check the
    confirmation form before saving rather than trusting it blindly."""
    if split_mode == SplitMode.EXACT:
        _validate_exact(amount_cents, resolved, warnings)
    elif split_mode == SplitMode.PERCENTAGE:
        _validate_percentage(resolved, warnings)
    elif split_mode == SplitMode.SHARES:
        _validate_shares(resolved, warnings)


def _validate_exact(
    amount_cents: int | None, resolved: list[ResolvedParticipant], warnings: list[str]
) -> None:
    if not resolved:
        return
    cents: list[int] = []
    for participant in resolved:
        if participant.value is None:
            warnings.append(
                "Не для всех участников распознана сумма при точном делении — "
                "проверьте и укажите вручную"
            )
            return
        try:
            cents.append(str_to_cents(participant.value))
        except ValueError:
            warnings.append(
                "Не удалось распознать одну из сумм участников — проверьте деление ниже"
            )
            return
    if amount_cents is None:
        return
    total = sum(cents)
    if total != amount_cents:
        warnings.append(
            "Суммы участников не совпадают с общей суммой расхода — "
            "проверьте и поправьте деление ниже"
        )


def _validate_percentage(resolved: list[ResolvedParticipant], warnings: list[str]) -> None:
    if not resolved:
        return
    total = Decimal(0)
    for participant in resolved:
        value = _parse_decimal(participant.value)
        if value is None:
            warnings.append(
                "Не для всех участников распознан процент — проверьте и укажите вручную"
            )
            return
        total += value
    if total != Decimal(100):
        warnings.append(
            f"Проценты участников в сумме дают {total}%, а не 100% — "
            "проверьте и поправьте деление ниже"
        )


def _validate_shares(resolved: list[ResolvedParticipant], warnings: list[str]) -> None:
    if not resolved:
        return
    total = Decimal(0)
    for participant in resolved:
        value = _parse_decimal(participant.value)
        if value is None or value <= 0:
            warnings.append(
                "Не все доли участников удалось распознать как положительные числа — "
                "проверьте и укажите вручную"
            )
            return
        total += value
    if total <= 0:
        warnings.append("Сумма долей участников должна быть больше нуля — проверьте деление ниже")


__all__ = ["build_draft"]
