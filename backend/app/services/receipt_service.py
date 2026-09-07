"""Receipt-photo-to-expense-draft orchestration.

The picture-shaped sibling of :mod:`app.services.voice_service`: a photo of a
cash receipt goes to GigaChat's vision path
(:func:`app.services.gigachat_service.extract_expense_from_receipt`) and the
resulting :class:`~app.schemas.voice.LLMExpenseExtraction` is resolved against
the group's real members and categories by the exact same shared code voice
notes use (:func:`app.services.voice_service.draft_from_extraction`). Like the
voice pipeline, this module never writes to the database — the draft only
becomes an expense once the user confirms it through the normal expense
creation flow.

A receipt says nothing about who owes whom, so the extraction prompt pins
``payer_name`` to "я" (whoever uploads the receipt paid it), ``split_mode`` to
``equal`` and ``participants`` to an empty list — the confirmation form then
defaults to "поровну между всеми", the same as a manual expense.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.models.group import Group
from app.models.user import User
from app.repositories import category_repo
from app.schemas.voice import LLMExpenseExtraction, VoiceExpenseDraftOut
from app.services import gigachat_service, voice_service

#: Image formats GigaChat's file store accepts for vision.
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png"})

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def build_draft(
    db: Session,
    *,
    group: Group,
    actor: User,
    image_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> VoiceExpenseDraftOut:
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_type == "image/jpg":  # частый нестандартный синоним
        normalized_type = "image/jpeg"
    if normalized_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequest("Загрузите чек как фото в формате JPEG или PNG")
    # Заголовок Content-Type — самодекларация клиента; magic bytes проверяют,
    # что в чужое хранилище не уедет произвольный файл под видом картинки.
    if not (image_bytes.startswith(_PNG_MAGIC) or image_bytes.startswith(_JPEG_MAGIC)):
        raise BadRequest("Файл не похож на фото — загрузите чек в формате JPEG или PNG")

    warnings: list[str] = []
    categories = category_repo.list_all(db)

    try:
        extraction = gigachat_service.extract_expense_from_receipt(
            image_bytes,
            filename=filename or "receipt.jpg",
            content_type=normalized_type,
            categories=categories,
        )
        llm_succeeded = True
    except gigachat_service.GigaChatError:
        warnings.append(
            "Твой AI помощник сейчас недоступен — заполните поля расхода вручную"
        )
        extraction = LLMExpenseExtraction()
        llm_succeeded = False

    if llm_succeeded and extraction.amount is None:
        warnings.append(
            "Не удалось прочитать итоговую сумму на чеке — укажите её вручную"
        )

    return voice_service.draft_from_extraction(
        db,
        group=group,
        actor=actor,
        extraction=extraction,
        llm_succeeded=llm_succeeded,
        # Черновик чека показывать нечего в поле «распознанный текст» — оно
        # для голосовой расшифровки; фронтенд для чека его не рендерит.
        transcript="",
        categories=categories,
        warnings=warnings,
    )


__all__ = ["ALLOWED_CONTENT_TYPES", "build_draft"]
