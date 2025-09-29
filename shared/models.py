"""
Pydantic models for request/response validation and data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, EmailStr, Field, validator


class ActionType(str, Enum):
    """Admin router action types."""
    CREATE_COURSE = "CREATE_COURSE"
    EDIT_COURSE = "EDIT_COURSE"
    DELETE_COURSE = "DELETE_COURSE"
    UPLOAD_LEARNERS_CSV = "UPLOAD_LEARNERS_CSV"
    UPLOAD_LEARNERS_CSV_DIRECT = "UPLOAD_LEARNERS_CSV_DIRECT"
    PREVIEW_CERTIFICATE = "PREVIEW_CERTIFICATE"
    LIST_COURSES = "LIST_COURSES"
    VIEW_LEARNERS = "VIEW_LEARNERS"
    ADD_ORGANIZATION = "ADD_ORGANIZATION"
    EDIT_ORGANIZATION = "EDIT_ORGANIZATION"
    DELETE_ORGANIZATION = "DELETE_ORGANIZATION"
    LIST_ORGANIZATIONS = "LIST_ORGANIZATIONS"
    RESEND_CERTIFICATE = "RESEND_CERTIFICATE"
    LIST_WEBHOOKS = "LIST_WEBHOOKS"
    RETRY_WEBHOOK = "RETRY_WEBHOOK"


class SOPActionType(str, Enum):
    """SOP router action types."""
    LIST_ORG_LEARNERS = "LIST_ORG_LEARNERS"
    DOWNLOAD_CERTIFICATE = "DOWNLOAD_CERTIFICATE"
    RESEND_CERTIFICATE = "RESEND_CERTIFICATE"


class CertificateSendStatus(str, Enum):
    """Certificate sending status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class WebhookStatus(str, Enum):
    """Webhook processing status."""
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class EmailStatus(str, Enum):
    """Email sending status."""
    SENT = "sent"
    FAILED = "failed"


class UserRole(str, Enum):
    """User roles."""
    ADMIN = "admin"
    SOP = "sop"


# Base Models
class BaseResponse(BaseModel):
    """Base response model."""
    ok: bool
    status: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None


class ActionRequest(BaseModel):
    """Base action request model."""
    action: Union[ActionType, SOPActionType]
    payload: Dict[str, Any]


# Course Models
class CreateCoursePayload(BaseModel):
    """Payload for creating a course."""
    course_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=500)
    certificate_template_html: str = Field(..., min_length=1)


class EditCoursePayload(BaseModel):
    """Payload for editing a course."""
    course_id: str = Field(..., min_length=1, max_length=255)
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    certificate_template_html: Optional[str] = Field(None, min_length=1)


class DeleteCoursePayload(BaseModel):
    """Payload for deleting a course."""
    course_id: str = Field(..., min_length=1, max_length=255)


class PreviewCertificatePayload(BaseModel):
    """Payload for previewing certificate."""
    course_id: str = Field(..., min_length=1, max_length=255)
    learner_name: str = Field(..., min_length=1)
    learner_email: EmailStr
    organization_website: str = Field(..., min_length=1)


class ListCoursesPayload(BaseModel):
    """Payload for listing courses."""
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ViewLearnersPayload(BaseModel):
    """Payload for viewing learners."""
    course_id: str = Field(..., min_length=1, max_length=255)
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


# Organization Models
class AddOrganizationPayload(BaseModel):
    """Payload for adding an organization."""
    website: str = Field(..., min_length=1, max_length=255)
    name: Optional[str] = Field(None, max_length=500)
    sop_email: EmailStr


class EditOrganizationPayload(BaseModel):
    """Payload for editing an organization."""
    website: str = Field(..., min_length=1, max_length=255)
    name: Optional[str] = Field(None, max_length=500)
    sop_email: Optional[EmailStr] = None


class DeleteOrganizationPayload(BaseModel):
    """Payload for deleting an organization."""
    website: str = Field(..., min_length=1, max_length=255)


# Learner Models
class LearnerCSVRow(BaseModel):
    """Single learner row from CSV."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    organization_website: str = Field(..., min_length=1, max_length=255)


class UploadLearnersCSVPayload(BaseModel):
    """Payload for uploading learners CSV."""
    course_id: str = Field(..., min_length=1, max_length=255)
    csv_file_id: str = Field(..., min_length=1)
    uploader: str = Field(..., min_length=1)  # Appwrite user ID


class UploadLearnersCSVDirectPayload(BaseModel):
    """Payload for uploading learners CSV data directly."""
    course_id: str = Field(..., min_length=1, max_length=255)
    csv_data: str = Field(..., min_length=1)  # CSV content as string


class CSVValidationResult(BaseModel):
    """Result of CSV validation."""
    valid_rows: List[LearnerCSVRow]
    invalid_rows: List[Dict[str, Any]]  # row_number, row_data, errors
    duplicate_rows: List[Dict[str, Any]]  # row_number, row_data


class EnrollmentResult(BaseModel):
    """Result of learner enrollment."""
    learner_email: EmailStr
    success: bool
    enrollment_id: Optional[str] = None
    error: Optional[str] = None


class UploadResult(BaseModel):
    """Result of CSV upload processing."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    created_learners: int
    enrollment_success: int
    enrollment_failed: int
    validation_errors: List[Dict[str, Any]]
    enrollment_errors: List[EnrollmentResult]


# Certificate Models
class ResendCertificatePayload(BaseModel):
    """Payload for resending certificate."""
    learner_email: Optional[EmailStr] = None
    organization_website: Optional[str] = None
    course_id: Optional[str] = None


# Webhook Models
class WebhookPayload(BaseModel):
    """Payload from Graphy webhook."""
    course_id: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    event_id: Optional[str] = Field(None, max_length=255)
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ListWebhooksPayload(BaseModel):
    """Payload for listing webhooks."""
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)
    status: Optional[WebhookStatus] = None


class RetryWebhookPayload(BaseModel):
    """Payload for retrying webhook."""
    webhook_event_id: str = Field(..., min_length=1)


# SOP Models
class ListOrgLearnersPayload(BaseModel):
    """Payload for listing organization learners."""
    organization_website: str = Field(..., min_length=1, max_length=255)
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class DownloadCertificatePayload(BaseModel):
    """Payload for downloading certificate."""
    learner_email: EmailStr
    course_id: str = Field(..., min_length=1, max_length=255)


# Database Models
class CourseModel(BaseModel):
    """Course database model."""
    id: str
    course_id: str
    name: str
    certificate_template_html: str
    created_at: datetime
    updated_at: datetime


class OrganizationModel(BaseModel):
    """Organization database model."""
    id: str
    website: str
    name: Optional[str] = None
    sop_email: EmailStr
    created_at: datetime
    updated_at: datetime


class LearnerModel(BaseModel):
    """Learner database model."""
    id: str
    name: str
    email: EmailStr
    organization_website: str
    course_id: str
    graphy_enrollment_id: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    completion_at: Optional[datetime] = None
    certificate_generated_at: Optional[datetime] = None
    certificate_sent_to_sop_at: Optional[datetime] = None
    certificate_send_status: Optional[CertificateSendStatus] = None
    certificate_file_id: Optional[str] = None
    last_resend_attempt: Optional[datetime] = None
    enrollment_error: Optional[str] = None


class WebhookEventModel(BaseModel):
    """Webhook event database model."""
    id: str
    source: str
    payload: str  # JSON string
    course_id: Optional[str] = None
    email: Optional[EmailStr] = None
    event_id: Optional[str] = None
    received_at: datetime
    processed_at: Optional[datetime] = None
    status: WebhookStatus
    attempts: int


class EmailLogModel(BaseModel):
    """Email log database model."""
    id: str
    to_email: EmailStr
    subject: str
    attachment_file_id: Optional[str] = None
    status: EmailStatus
    response: Optional[str] = None
    created_at: datetime
    retry_count: int


# Service Models
class GraphyEnrollmentRequest(BaseModel):
    """Request to Graphy enrollment API."""
    course_id: str
    email: EmailStr
    name: str
    metadata: Optional[Dict[str, Any]] = None


class GraphyEnrollmentResponse(BaseModel):
    """Response from Graphy enrollment API."""
    ok: bool
    enrollment_id: Optional[str] = None
    error: Optional[str] = None


class EmailRequest(BaseModel):
    """Email sending request."""
    to_email: EmailStr
    subject: str
    body: str
    attachment_file_id: Optional[str] = None
    attachment_filename: Optional[str] = None


class EmailResponse(BaseModel):
    """Email sending response."""
    ok: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class PDFGenerationRequest(BaseModel):
    """PDF generation request."""
    html_content: str
    filename: str


class PDFGenerationResponse(BaseModel):
    """PDF generation response."""
    ok: bool
    file_id: Optional[str] = None
    error: Optional[str] = None


# Certificate Template Context
class CertificateContext(BaseModel):
    """Context for certificate template rendering."""
    learner_name: str
    course_name: str
    completion_date: str  # ISO format
    organization: str
    learner_email: EmailStr
    custom_fields: Optional[Dict[str, str]] = None

    @validator('completion_date')
    def validate_completion_date(cls, v):
        """Validate completion date is ISO format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('completion_date must be in ISO format')


# Auth Models
class AuthContext(BaseModel):
    """Authentication context."""
    user_id: str
    role: UserRole
    organization_website: Optional[str] = None  # For SOP users


class JWTPayload(BaseModel):
    """JWT payload structure."""
    user_id: str
    role: UserRole
    organization_website: Optional[str] = None
    exp: int
    iat: int
