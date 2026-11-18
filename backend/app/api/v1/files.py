"""
Vault City Files API:
- POST   /api/v1/files/upload          Upload -> Quarantine S3 -> Async Scan, Promote & pgvector Index
- GET    /api/v1/files                 List authenticated user's files + storage quota usage
- GET    /api/v1/files/activity/logs   Fetch user's real audit logs from PostgreSQL
- GET    /api/v1/files/{file_id}       Get single file metadata & live scan status
- GET    /api/v1/files/{file_id}/content  View (inline) or Download (attachment) verified file from Secured S3
- PATCH  /api/v1/files/{file_id}       Rename or update file metadata
- DELETE /api/v1/files/{file_id}       Delete file from S3, pgvector document_chunks, and PostgreSQL
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import rate_limit
from app.core.pipeline_logger import log_file_event
from app.core.security import get_current_active_user
from app.models.audit_log import AuditLog
from app.models.file import FileDocument
from app.models.user import User
from app.schemas.file import FileDocumentUpdate
from app.services.ingestion_service import compute_sha256, process_uploaded_file
from app.services.s3_service import s3_service, sanitize_filename
from app.services.vector_service import vector_service

router = APIRouter(prefix="/files", tags=["Vault Files & Storage"])

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".json",
}

ALLOWED_CATEGORIES = {"Identity", "Financial", "Medical", "Personal", "Other"}


def _serialize_file(file_doc: FileDocument) -> Dict[str, Any]:
    """Serialize FileDocument ORM row for frontend VaultView & preview modal."""
    is_ready = file_doc.scan_status == "indexed"
    content_url = f"/api/v1/files/{file_doc.id}/content" if is_ready else None
    download_url = f"/api/v1/files/{file_doc.id}/content?download=true" if is_ready else None

    # Normalize scan_status into UI-friendly status + preserve exact scan_status
    ui_status = "indexed"
    if file_doc.scan_status in ("scanning", "classifying"):
        ui_status = file_doc.scan_status
    elif file_doc.scan_status != "indexed":
        ui_status = "failed"

    scan_report = None
    if file_doc.pages_json:
        try:
            parsed = json.loads(file_doc.pages_json)
            if isinstance(parsed, dict):
                scan_report = parsed
        except (ValueError, TypeError):
            scan_report = None

    return {
        "id": str(file_doc.id),
        "user_id": str(file_doc.user_id),
        "filename": file_doc.filename,
        "original_filename": file_doc.original_filename,
        "file_size": file_doc.file_size,
        "mime_type": file_doc.mime_type,
        "sha256_hash": file_doc.sha256_hash,
        "scan_status": file_doc.scan_status,
        "status": ui_status,
        "category": file_doc.category,
        "document_type": file_doc.document_type,
        "description": file_doc.description,
        "scan_report": scan_report,
        "is_pii": file_doc.is_pii,
        "page_count": file_doc.page_count,
        "s3_key": file_doc.s3_key if is_ready else None,
        "preview_url": content_url,
        "download_url": download_url,
        "created_at": file_doc.created_at.isoformat() if file_doc.created_at else None,
        "updated_at": file_doc.updated_at.isoformat() if file_doc.updated_at else None,
    }


def _parse_uuid_or_400(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file identifier.",
        )


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload file to Quarantine S3, verify SHA-256 dedup, and trigger scan + promotion",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, key_prefix="file_upload"))],
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    custom_name: Optional[str] = Form(None),
    category: str = Form("Other"),
    sync: bool = Query(False, description="Wait for scan & vectorization to complete before returning"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Validate file size, extension, and per-user storage quota.
    2. Compute SHA-256 and check per-user deduplication.
    3. Stage raw file into isolated `vault-quarantine` S3 bucket.
    4. Record `files` row (`scan_status='scanning'`) & `audit_logs`.
    5. Run antivirus + ML security scan + promotion to `vault-secured` + pgvector indexing.
    """
    original_name = (file.filename or "document.bin").strip()
    display_name = (custom_name or original_name).strip() or original_name
    ext = os.path.splitext(original_name.lower())[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Ensure display_name keeps the original extension if user renamed without extension
    if not os.path.splitext(display_name)[1] and ext:
        display_name = f"{display_name}{ext}"

    resolved_category = category if category in ALLOWED_CATEGORIES else "Other"

    data = await file.read()
    file_size = len(data)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {max_mb} MB.",
        )

    # Check user storage quota
    quota_res = await db.execute(
        select(func.coalesce(func.sum(FileDocument.file_size), 0)).where(
            FileDocument.user_id == current_user.id,
            FileDocument.scan_status.in_(["scanning", "classifying", "indexed"]),
        )
    )
    used_bytes = int(quota_res.scalar_one() or 0)
    if used_bytes + file_size > settings.USER_STORAGE_QUOTA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Storage quota exceeded (500 MB limit). Delete unused files to free space.",
        )

    # Compute SHA-256 fingerprint & perform strict per-user deduplication
    sha256_hex = compute_sha256(data)
    dup_res = await db.execute(
        select(FileDocument).where(
            FileDocument.user_id == current_user.id,
            FileDocument.sha256_hash == sha256_hex,
            FileDocument.scan_status.in_(["scanning", "classifying", "indexed"]),
        ).limit(1)
    )
    existing = dup_res.scalar_one_or_none()
    if existing:
        log_file_event(
            "DEDUP_CONFLICT",
            "rejected",
            f"Duplicate SHA-256 already exists as {existing.filename!r}",
            file_id=str(existing.id),
            user_id=str(current_user.id),
            filename=display_name,
            details={"sha256": sha256_hex, "existing_filename": existing.filename},
            level="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate file detected: this exact file is already in your vault as '{existing.filename}'.",
        )

    file_id = uuid.uuid4()
    mime_type = file.content_type or "application/octet-stream"

    log_file_event(
        "UPLOAD_RECEIVED",
        "accepted",
        f"Received {file_size} bytes ({mime_type}); SHA-256={sha256_hex[:16]}…",
        file_id=str(file_id),
        user_id=str(current_user.id),
        filename=display_name,
        details={"size": file_size, "mime_type": mime_type, "sha256": sha256_hex, "category": resolved_category},
    )

    # Stage untrusted upload into isolated Quarantine S3 bucket
    try:
        quarantine_key = await s3_service.upload_to_quarantine(
            user_id=str(current_user.id),
            file_id=str(file_id),
            filename=display_name,
            data=data,
            content_type=mime_type,
            sha256_hex=sha256_hex,
        )
    except Exception as exc:
        log_file_event(
            "QUARANTINE_S3",
            "failed",
            f"Failed to upload to {settings.S3_QUARANTINE_BUCKET}: {exc}",
            file_id=str(file_id),
            user_id=str(current_user.id),
            filename=display_name,
            level="ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to stage file in quarantine storage: {exc}",
        )

    log_file_event(
        "QUARANTINE_S3",
        "staged",
        f"Staged in {settings.S3_QUARANTINE_BUCKET}/{quarantine_key} — queuing ClamAV + Vision/OCR + Security scan",
        file_id=str(file_id),
        user_id=str(current_user.id),
        filename=display_name,
        details={"quarantine_key": quarantine_key},
    )

    new_file = FileDocument(
        id=file_id,
        user_id=current_user.id,
        filename=display_name,
        original_filename=original_name,
        s3_key=quarantine_key,
        file_size=file_size,
        mime_type=mime_type,
        sha256_hash=sha256_hex,
        scan_status="scanning",
        category=resolved_category,
        document_type="Pending Security Scan",
        description="Staged in isolated quarantine — antivirus & ML security scan in progress...",
        is_pii=(resolved_category == "Identity"),
        page_count=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_file)
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=current_user.id,
            action="file_uploaded_quarantine",
            resource_type="file",
            resource_id=str(file_id),
            status="info",
            details={
                "filename": display_name,
                "size": file_size,
                "sha256": sha256_hex,
                "category": resolved_category,
            },
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()
    await db.refresh(new_file)

    if sync:
        await process_uploaded_file(file_id, current_user.id, quarantine_key)
        await db.refresh(new_file)
    else:
        background_tasks.add_task(process_uploaded_file, file_id, current_user.id, quarantine_key)

    return _serialize_file(new_file)


@router.get(
    "",
    summary="List all files owned by the authenticated user with storage stats",
)
async def list_files(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(FileDocument)
        .where(FileDocument.user_id == current_user.id)
        .order_by(desc(FileDocument.created_at))
    )
    if category and category != "All":
        stmt = stmt.where(FileDocument.category == category)

    result = await db.execute(stmt)
    files = list(result.scalars().all())

    if search and search.strip():
        q = search.strip().lower()
        files = [
            f
            for f in files
            if q in (f.filename or "").lower()
            or q in (f.description or "").lower()
            or q in (f.document_type or "").lower()
        ]

    used_bytes = sum(f.file_size for f in files if f.scan_status in ("scanning", "classifying", "indexed"))

    return {
        "files": [_serialize_file(f) for f in files],
        "total_count": len(files),
        "used_bytes": used_bytes,
        "quota_bytes": settings.USER_STORAGE_QUOTA_BYTES,
    }


@router.get(
    "/activity/logs",
    summary="Fetch real audit & security activity logs for the authenticated user",
)
async def get_activity_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    action_labels = {
        "file_uploaded_quarantine": "Staged in Quarantine S3",
        "file_scanned_and_indexed": "Verified, Promoted & Indexed",
        "file_indexed_pgvector": "Verified, Promoted & Indexed",
        "file_virus_blocked": "Malware Blocked by ClamAV",
        "file_infected": "Malware Blocked by ClamAV",
        "file_blocked_sqli": "SQL Injection Blocked",
        "file_blocked_prompt_injection": "Prompt Injection Blocked",
        "file_blocked_sqli_and_prompt_injection": "Security Threat Blocked",
        "file_integrity_mismatch": "SHA-256 Integrity Mismatch",
        "file_processing_failed": "File Processing Failed",
        "file_renamed": "Document Renamed",
        "file_deleted": "File Permanently Deleted",
    }

    items = []
    for log in logs:
        details = log.details or {}
        target = (
            details.get("filename")
            or details.get("threat_name")
            or details.get("error")
            or log.resource_id
            or log.resource_type
        )
        ui_status = "info"
        if log.status == "success":
            ui_status = "success"
        elif log.status in ("blocked", "error", "failed"):
            ui_status = "warning"

        items.append(
            {
                "id": str(log.id),
                "action": action_labels.get(log.action, log.action.replace("_", " ").title()),
                "target": str(target),
                "timestamp": log.created_at.isoformat() if log.created_at else datetime.utcnow().isoformat(),
                "status": ui_status,
            }
        )

    return {"activities": items}


@router.get(
    "/{file_id}",
    summary="Get single file metadata and live scan status",
)
async def get_file_metadata(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_uuid_or_400(file_id)
    res = await db.execute(
        select(FileDocument).where(
            FileDocument.id == uid,
            FileDocument.user_id == current_user.id,
        )
    )
    file_doc = res.scalar_one_or_none()
    if not file_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return _serialize_file(file_doc)


@router.get(
    "/{file_id}/content",
    summary="View or download a verified file strictly from Secured S3",
)
async def get_file_content(
    file_id: str,
    download: bool = Query(False, description="Set true for attachment download, false for inline view"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_uuid_or_400(file_id)
    res = await db.execute(
        select(FileDocument).where(
            FileDocument.id == uid,
            FileDocument.user_id == current_user.id,
        )
    )
    file_doc = res.scalar_one_or_none()
    if not file_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    if file_doc.scan_status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"File is not available for access (current status: {file_doc.scan_status}).",
        )

    try:
        file_bytes, content_type = await s3_service.download_from_secured(file_doc.s3_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secured file object could not be retrieved from storage: {exc}",
        )

    safe_name = sanitize_filename(file_doc.filename)
    disposition = "attachment" if download else "inline"

    log_file_event(
        "FILE_DOWNLOADED" if download else "FILE_VIEWED",
        "served",
        f"Served {len(file_bytes)} bytes from {settings.S3_SECURED_BUCKET} ({disposition})",
        file_id=str(file_doc.id),
        user_id=str(current_user.id),
        filename=file_doc.filename,
        details={"bytes": len(file_bytes), "disposition": disposition},
    )

    return Response(
        content=file_bytes,
        media_type=file_doc.mime_type or content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=60",
        },
    )


@router.patch(
    "/{file_id}",
    summary="Rename or update file metadata",
)
async def update_file_metadata(
    file_id: str,
    payload: FileDocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_uuid_or_400(file_id)
    res = await db.execute(
        select(FileDocument).where(
            FileDocument.id == uid,
            FileDocument.user_id == current_user.id,
        )
    )
    file_doc = res.scalar_one_or_none()
    if not file_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    old_name = file_doc.filename
    if payload.filename is not None and payload.filename.strip():
        file_doc.filename = payload.filename.strip()
    if payload.category is not None and payload.category in ALLOWED_CATEGORIES:
        file_doc.category = payload.category
    if payload.description is not None:
        file_doc.description = payload.description.strip()
    if payload.is_pii is not None:
        file_doc.is_pii = payload.is_pii

    file_doc.updated_at = datetime.utcnow()
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=current_user.id,
            action="file_renamed",
            resource_type="file",
            resource_id=str(file_doc.id),
            status="info",
            details={"old_name": old_name, "filename": file_doc.filename},
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()
    await db.refresh(file_doc)
    return _serialize_file(file_doc)


@router.delete(
    "/{file_id}",
    summary="Delete file from S3, pgvector chunks, and PostgreSQL",
)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_uuid_or_400(file_id)
    res = await db.execute(
        select(FileDocument).where(
            FileDocument.id == uid,
            FileDocument.user_id == current_user.id,
        )
    )
    file_doc = res.scalar_one_or_none()
    if not file_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    filename = file_doc.filename
    s3_key = file_doc.s3_key
    was_indexed = file_doc.scan_status == "indexed"

    # Remove S3 object from whichever bucket currently holds it
    if s3_key:
        if was_indexed and s3_key.startswith("vault/"):
            await s3_service.delete_from_secured(s3_key)
        else:
            await s3_service.delete_from_quarantine(s3_key)

    # Remove vector chunks & file DB row
    await vector_service.delete_file_chunks(db=db, file_id=uid, user_id=current_user.id)
    await db.delete(file_doc)
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=current_user.id,
            action="file_deleted",
            resource_type="file",
            resource_id=str(uid),
            status="warning",
            details={"filename": filename},
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()
    log_file_event(
        "FILE_DELETED",
        "deleted",
        "Deleted from S3, PostgreSQL pgvector chunks, and files table",
        file_id=str(uid),
        user_id=str(current_user.id),
        filename=filename,
        details={"s3_key": s3_key},
        level="WARNING",
    )

    return {"status": "deleted", "id": str(uid), "filename": filename}
