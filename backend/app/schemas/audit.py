"""
Pydantic schemas for security audit logs and telemetry.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    """Schema for recording an audit log event."""
    action: str = Field(..., max_length=64)
    resource_type: str = Field(..., max_length=64)
    resource_id: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=64)
    user_agent: Optional[str] = None
    status: str = Field("success", max_length=32)
    details: Optional[Dict[str, Any]] = None


class AuditLogResponse(BaseModel):
    """Audit log entry response representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
