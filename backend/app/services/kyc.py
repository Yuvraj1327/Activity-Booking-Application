"""Owner KYC: submission by the owner, review by an admin.

* Documents live in the PRIVATE `kyc-documents` bucket. No public URL and no client-side storage
  policy exists; only this backend (service-role key) reads or writes objects.
* The file type is sniffed from its bytes (PDF / JPEG / PNG); the declared type is not trusted.
* Every admin view of a document is written to the audit log.
* What counts as a sufficient set of documents is an open decision (N11): this module records and
  reviews whatever is submitted and never blocks other features on it by itself.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import OwnerKycDocument, OwnerProfile, Profile
from app.services import audit
from app.services.notifications import NotificationService
from app.services.storage import StorageGateway

MAX_BYTES = 5 * 1024 * 1024
MAX_DOCS = 20
DOC_TYPES = ("identity", "address", "business_registration", "gst", "bank_account", "other")


def sniff(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    return None


def doc_out(d: OwnerKycDocument) -> dict[str, Any]:
    """Never includes the storage path."""
    return {
        "id": d.id, "doc_type": d.doc_type, "original_filename": d.original_filename,
        "content_type": d.content_type, "byte_size": d.byte_size, "status": d.status,
        "rejection_reason": d.rejection_reason, "reviewed_at": d.reviewed_at, "created_at": d.created_at,
    }  # fmt: skip


class KycService:
    def __init__(self, session: AsyncSession, settings: Settings, storage: StorageGateway) -> None:
        self.s = session
        self.settings = settings
        self.storage = storage
        self.bucket = settings.supabase_storage_bucket_kyc

    # ================================================================== owner side
    async def owner_view(self, owner_id: UUID) -> dict[str, Any]:
        owner = await self.s.get(OwnerProfile, owner_id)
        assert owner is not None
        docs = (
            await self.s.scalars(
                select(OwnerKycDocument)
                .where(OwnerKycDocument.owner_id == owner_id)
                .order_by(OwnerKycDocument.created_at.desc())
            )
        ).all()
        return {
            "kyc_status": owner.kyc_status,
            "kyc_note": owner.kyc_note if owner.kyc_status == "rejected" else None,
            "documents": [doc_out(d) for d in docs],
            "accepted_types": list(DOC_TYPES),
            "max_bytes": MAX_BYTES,
        }

    async def upload(
        self, owner_id: UUID, doc_type: str, filename: str | None, data: bytes
    ) -> dict[str, Any]:
        if doc_type not in DOC_TYPES:
            raise ValidationFailedError("Unknown document type.", code="INVALID_DOC_TYPE")
        if not data:
            raise ValidationFailedError("The file is empty.", code="EMPTY_FILE")
        if len(data) > MAX_BYTES:
            raise ValidationFailedError("Documents can be at most 5 MB.", code="FILE_TOO_LARGE")
        kind = sniff(data)
        if kind is None:
            raise ValidationFailedError("Upload a PDF, JPEG or PNG file.", code="UNSUPPORTED_FILE_TYPE")
        ext, ctype = kind
        owner = await self.s.scalar(
            select(OwnerProfile).where(OwnerProfile.user_id == owner_id).with_for_update()
        )
        assert owner is not None
        count = int(
            await self.s.scalar(select(func.count()).where(OwnerKycDocument.owner_id == owner_id)) or 0
        )
        if count >= MAX_DOCS:
            raise ConflictError("Too many documents. Delete one first.", code="TOO_MANY_DOCUMENTS")
        path = f"{owner_id}/{uuid.uuid4().hex}.{ext}"
        await self.storage.upload(path, data, ctype, bucket=self.bucket)
        safe_name = (filename or "document")[:120].replace("\r", " ").replace("\n", " ")
        doc = OwnerKycDocument(
            owner_id=owner_id, doc_type=doc_type, storage_path=path, original_filename=safe_name,
            content_type=ctype, byte_size=len(data),
        )  # fmt: skip
        self.s.add(doc)
        before = owner.kyc_status
        if owner.kyc_status in ("not_submitted", "rejected"):
            owner.kyc_status = "pending"
        await self.s.flush()
        audit.record(self.s, None, "owner.kyc_document_uploaded", "owner_kyc_document", doc.id,
                     before={"kyc_status": before}, after={"kyc_status": owner.kyc_status, "doc_type": doc_type})  # fmt: skip
        await self.s.commit()
        return doc_out(doc)

    async def delete_own(self, owner_id: UUID, doc_id: UUID) -> None:
        doc = await self.s.scalar(
            select(OwnerKycDocument)
            .where(OwnerKycDocument.id == doc_id, OwnerKycDocument.owner_id == owner_id)
            .with_for_update()
        )
        if doc is None:
            raise NotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")
        if doc.status != "pending":
            raise ConflictError("A reviewed document cannot be deleted.", code="DOCUMENT_REVIEWED")
        path = doc.storage_path
        await self.s.delete(doc)
        await self.s.commit()
        await self.storage.delete([path], bucket=self.bucket)

    # ================================================================== admin side
    async def queue(self, limit: int, offset: int) -> dict[str, Any]:
        pending = (
            select(func.count()).where(OwnerKycDocument.owner_id == Profile.id, OwnerKycDocument.status == "pending")
            .correlate(Profile).scalar_subquery()
        )  # fmt: skip
        oldest = (
            select(func.min(OwnerKycDocument.created_at)).where(OwnerKycDocument.owner_id == Profile.id, OwnerKycDocument.status == "pending")
            .correlate(Profile).scalar_subquery()
        )  # fmt: skip
        rows = (
            await self.s.execute(
                select(
                    Profile.id,
                    Profile.full_name,
                    OwnerProfile.business_name,
                    OwnerProfile.kyc_status,
                    pending,
                    oldest,
                )
                .join(OwnerProfile, OwnerProfile.user_id == Profile.id)
                .where(Profile.role == "owner", pending > 0)
                .order_by(oldest, Profile.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return {
            "items": [
                {"owner_id": i, "owner_name": n, "business_name": b, "kyc_status": k, "pending_documents": int(p), "waiting_since": o}
                for i, n, b, k, p, o in rows[:limit]
            ],
            "limit": limit, "offset": offset, "has_more": len(rows) > limit,
        }  # fmt: skip

    async def admin_view(self, owner_id: UUID) -> dict[str, Any]:
        owner = await self.s.get(OwnerProfile, owner_id)
        if owner is None:
            raise NotFoundError("Owner not found.", code="OWNER_NOT_FOUND")
        view = await self.owner_view(owner_id)
        view["kyc_note"] = owner.kyc_note
        view["kyc_reviewed_at"] = owner.kyc_reviewed_at
        return view

    async def read_file(self, actor: CurrentUser, doc_id: UUID) -> tuple[bytes, str, str]:
        doc = await self.s.get(OwnerKycDocument, doc_id)
        if doc is None:
            raise NotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")
        data = await self.storage.download(doc.storage_path, self.bucket)
        audit.record(self.s, actor.profile, "admin.kyc_document_viewed", "owner_kyc_document", doc.id,
                     owner_id=str(doc.owner_id), doc_type=doc.doc_type)  # fmt: skip
        await self.s.commit()
        ext = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[doc.content_type]
        return data, doc.content_type, f"kyc-{str(doc.id)[:8]}.{ext}"

    async def review_document(
        self, actor: CurrentUser, doc_id: UUID, decision: str, reason: str | None
    ) -> dict[str, Any]:
        doc = await self.s.scalar(
            select(OwnerKycDocument).where(OwnerKycDocument.id == doc_id).with_for_update()
        )
        if doc is None:
            raise NotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")
        if doc.status != "pending":
            raise ConflictError("This document has already been reviewed.", code="DOCUMENT_REVIEWED")
        before = {"status": doc.status}
        doc.status = decision
        doc.rejection_reason = reason if decision == "rejected" else None
        doc.reviewed_by = actor.id
        doc.reviewed_at = datetime.now(UTC)
        audit.record(self.s, actor.profile, f"admin.kyc_document_{decision}", "owner_kyc_document", doc.id,
                     before=before, after={"status": decision}, reason=reason, owner_id=str(doc.owner_id))  # fmt: skip
        await NotificationService(self.s).queue(
            user_id=doc.owner_id, type_="kyc.document",
            title="Document " + decision, body=(reason or f"Your {doc.doc_type.replace('_', ' ')} document was {decision}.")[:500],
            dedupe_key=f"kyc:{doc.id}:{decision}",
        )  # fmt: skip
        await self.s.commit()
        return doc_out(doc)

    async def decide_owner(
        self, actor: CurrentUser, owner_id: UUID, decision: str, reason: str | None
    ) -> dict[str, Any]:
        owner = await self.s.scalar(
            select(OwnerProfile).where(OwnerProfile.user_id == owner_id).with_for_update()
        )
        if owner is None:
            raise NotFoundError("Owner not found.", code="OWNER_NOT_FOUND")
        counts = dict(
            (
                await self.s.execute(
                    select(OwnerKycDocument.status, func.count())
                    .where(OwnerKycDocument.owner_id == owner_id)
                    .group_by(OwnerKycDocument.status)
                )
            ).all()
        )
        if decision == "verified":
            if counts.get("pending", 0):
                raise ConflictError("Review every pending document first.", code="DOCUMENTS_PENDING")
            if not counts.get("approved", 0):
                raise ConflictError("At least one approved document is needed.", code="NO_APPROVED_DOCUMENT")
        before = {"kyc_status": owner.kyc_status}
        owner.kyc_status = decision
        owner.kyc_reviewed_at = datetime.now(UTC)
        owner.kyc_reviewed_by = actor.id
        owner.kyc_note = reason
        audit.record(self.s, actor.profile, f"admin.kyc_{decision}", "owner", owner_id, before=before,
                     after={"kyc_status": decision}, reason=reason)  # fmt: skip
        await NotificationService(self.s).queue(
            user_id=owner_id, type_="kyc.decision", title=f"Verification {decision}",
            body=(reason or "Your business verification is complete.")[:500],
            dedupe_key=f"kyc-owner:{owner_id}:{decision}:{owner.kyc_reviewed_at.isoformat()}",
        )  # fmt: skip
        await self.s.commit()
        return {"owner_id": owner_id, "kyc_status": decision}
