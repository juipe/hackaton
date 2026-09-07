"""Receipt expense draft endpoint.

Membership-scoped like every other group route. This never creates an
expense — it only returns an ephemeral draft for the frontend to confirm
before posting through the existing ``POST /groups/{group_id}/expenses``
route (the same contract as the voice endpoint next door).

Defined as a sync ``def`` (not ``async``) so FastAPI runs it in a threadpool —
the GigaChat upload and completion are blocking HTTP calls that must not block
the event loop.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, Membership
from app.core.errors import BadRequest
from app.schemas.voice import VoiceExpenseDraftOut
from app.services import receipt_service

router = APIRouter(tags=["Загрузка чека"])


@router.post(
    "/groups/{group_id}/receipt-expenses",
    response_model=VoiceExpenseDraftOut,
    summary="Черновик расхода из фото чека",
)
def create_receipt_expense_draft(
    group_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    membership: Membership,
    receipt: UploadFile = File(..., description="Фото кассового чека (JPEG или PNG)"),
) -> VoiceExpenseDraftOut:
    # Читаем не больше лимита плюс один байт: лишний байт выдаёт превышение,
    # а многогигабайтный аплоад не материализуется в память целиком.
    raw = receipt.file.read(settings.receipt_max_upload_bytes + 1)
    if not raw:
        raise BadRequest("Пустой файл чека")
    if len(raw) > settings.receipt_max_upload_bytes:
        raise BadRequest("Фото чека слишком большое")
    return receipt_service.build_draft(
        db,
        group=membership.group,
        actor=user,
        image_bytes=raw,
        filename=receipt.filename,
        content_type=receipt.content_type,
    )


__all__ = ["router"]
