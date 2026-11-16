"""
Application Pydantic Schemas Package.
Centralized definitions for data validation, request parsing, and response serialization.
"""
from app.schemas.audit import (
    AuditLogCreate,
    AuditLogResponse,
)
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    PasswordResetResponse,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.schemas.conversation import (
    ChatMessageCreate,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
)
from app.schemas.file import (
    DocumentPageSchema,
    FileDocumentBase,
    FileDocumentCreate,
    FileDocumentResponse,
    FileDocumentUpdate,
)
from app.schemas.turnstile import (
    TurnstileVerifyRequest,
    TurnstileVerifyResponse,
)
from app.schemas.user import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserBase,
    UserResponse,
    make_user_response,
)

__all__ = [
    # Turnstile
    "TurnstileVerifyRequest",
    "TurnstileVerifyResponse",
    # User
    "UserBase",
    "UserResponse",
    "UpdateProfileRequest",
    "ChangePasswordRequest",
    "make_user_response",
    # Auth
    "UserRegisterRequest",
    "UserLoginRequest",
    "GoogleAuthRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "PasswordResetResponse",
    "AuthResponse",
    # File
    "DocumentPageSchema",
    "FileDocumentBase",
    "FileDocumentCreate",
    "FileDocumentUpdate",
    "FileDocumentResponse",
    # Conversation
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ConversationCreate",
    "ConversationResponse",
    # Audit
    "AuditLogCreate",
    "AuditLogResponse",
]
