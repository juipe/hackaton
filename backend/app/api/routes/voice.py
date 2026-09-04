"""Voice expense draft endpoint.

Membership-scoped like every other group route. This never creates an
expense — it only returns an ephemeral draft for the frontend to confirm
(and resolve, where ambiguous) before posting through the existing
``POST /groups/{group_id}/expenses`` route.

Defined as a sync ``def`` (not ``async``) so FastAPI runs it in a threadpool —
Whisper transcription and the Ollama call are both blocking, CPU/IO-bound
work that must not block the event loop.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, Membership
from app.core.errors import BadRequest
from app.schemas.voice import VoiceExpenseDraftOut
from app.services import voice_service

router = APIRouter(tags=["Голосовой ввод"])


@router.post(
    "/groups/{group_id}/voice-expenses",
    response_model=VoiceExpenseDraftOut,
    summary="Черновик расхода из голосовой записи",
)
def create_voice_expense_draft(
    group_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    membership: Membership,
    audio: UploadFile = File(..., description="Аудиозапись голосового ввода"),
) -> VoiceExpenseDraftOut:
    raw = audio.file.read()
    if not raw:
        raise BadRequest("Пустая аудиозапись")
    if len(raw) > settings.voice_max_upload_bytes:
        raise BadRequest("Аудиозапись слишком большая")
    return voice_service.build_draft(db, group=membership.group, actor=user, audio_bytes=raw)


__all__ = ["router"]
