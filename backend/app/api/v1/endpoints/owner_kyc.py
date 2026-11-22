"""Owner side of KYC: submit and track verification documents."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status

from app.api.deps import DbSession, OwnerUser
from app.core.errors import ValidationFailedError
from app.services.kyc import MAX_BYTES, KycService

router = APIRouter(prefix="/owners/kyc", tags=["owner-kyc"])


def _svc(request: Request, session: DbSession) -> KycService:
    return KycService(session, request.app.state.settings, request.app.state.storage)


@router.get("", summary="My verification status and submitted documents")
async def my_kyc(request: Request, user: OwnerUser, session: DbSession) -> dict:
    return await _svc(request, session).owner_view(user.id)


@router.post("/documents", status_code=status.HTTP_201_CREATED, summary="Upload a verification document")
async def upload_document(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValidationFailedError("Documents can be at most 5 MB.", code="FILE_TOO_LARGE")
    return await _svc(request, session).upload(user.id, doc_type, file.filename, data)


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a document that is still pending",
)
async def delete_document(doc_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> Response:
    await _svc(request, session).delete_own(user.id, doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
