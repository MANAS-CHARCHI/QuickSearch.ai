"""
Pydantic schemas for FileDocument storage, indexing, and metadata.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentPageSchema(BaseModel):
    """Individual page preview schema."""
    page_number: int = Field(..., ge=1)
    url: str
    name: Optional[str] = None
    size: Optional[int] = None


class FileDocumentBase(BaseModel):
    """Shared file document properties."""
    filename: str = Field(..., max_length=255)
    original_filename: str = Field(..., max_length=255)
    mime_type: str = Field(..., max_length=128)
    category: str = Field("Other", max_length=64)
    document_type: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    is_pii: bool = False
    page_count: int = Field(1, ge=1)


class FileDocumentCreate(FileDocumentBase):
    """Schema for creating a new file record."""
    s3_key: str = Field(..., max_length=512)
    file_size: int = Field(..., ge=0)
    sha256_hash: str = Field(..., min_length=64, max_length=64)
    scan_status: str = Field("clean", max_length=32)
    pages_json: Optional[str] = None


class FileDocumentUpdate(BaseModel):
    """Schema for updating file metadata."""
    filename: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=64)
    document_type: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    is_pii: Optional[bool] = None


class FileDocumentResponse(FileDocumentBase):
    """File document response representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    s3_key: str
    file_size: int
    sha256_hash: str
    scan_status: str
    pages: Optional[List[DocumentPageSchema]] = None
    created_at: datetime
    updated_at: datetime
