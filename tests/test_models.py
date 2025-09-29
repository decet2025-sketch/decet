"""
Unit tests for Pydantic models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from shared.models import (
    ActionRequest, ActionType, SOPActionType,
    CreateCoursePayload, EditCoursePayload, DeleteCoursePayload,
    PreviewCertificatePayload, ListCoursesPayload, ViewLearnersPayload,
    AddOrganizationPayload, EditOrganizationPayload, DeleteOrganizationPayload,
    UploadLearnersCSVPayload, ResendCertificatePayload, ListWebhooksPayload,
    RetryWebhookPayload, LearnerCSVRow, CSVValidationResult, UploadResult,
    EnrollmentResult, CertificateContext, WebhookPayload,
    ListOrgLearnersPayload, DownloadCertificatePayload,
    CourseModel, OrganizationModel, LearnerModel, WebhookEventModel,
    EmailLogModel, CertificateSendStatus, WebhookStatus, EmailStatus,
    UserRole, GraphyEnrollmentRequest, GraphyEnrollmentResponse,
    EmailRequest, EmailResponse, PDFGenerationRequest, PDFGenerationResponse,
    AuthContext, JWTPayload
)


class TestActionRequest:
    """Test ActionRequest model."""
    
    def test_valid_admin_action(self):
        """Test valid admin action request."""
        request = ActionRequest(
            action=ActionType.CREATE_COURSE,
            payload={"course_id": "test-123", "name": "Test Course"}
        )
        assert request.action == ActionType.CREATE_COURSE
        assert request.payload == {"course_id": "test-123", "name": "Test Course"}
    
    def test_valid_sop_action(self):
        """Test valid SOP action request."""
        request = ActionRequest(
            action=SOPActionType.LIST_ORG_LEARNERS,
            payload={"organization_website": "example.com"}
        )
        assert request.action == SOPActionType.LIST_ORG_LEARNERS
        assert request.payload == {"organization_website": "example.com"}
    
    def test_invalid_action(self):
        """Test invalid action raises validation error."""
        with pytest.raises(ValidationError):
            ActionRequest(
                action="INVALID_ACTION",
                payload={}
            )


class TestCourseModels:
    """Test course-related models."""
    
    def test_create_course_payload(self):
        """Test CreateCoursePayload validation."""
        payload = CreateCoursePayload(
            course_id="test-123",
            name="Test Course",
            certificate_template_html="<html><body>Certificate</body></html>"
        )
        assert payload.course_id == "test-123"
        assert payload.name == "Test Course"
        assert "Certificate" in payload.certificate_template_html
    
    def test_create_course_payload_validation(self):
        """Test CreateCoursePayload validation errors."""
        with pytest.raises(ValidationError):
            CreateCoursePayload(
                course_id="",  # Empty course_id should fail
                name="Test Course",
                certificate_template_html="<html></html>"
            )
        
        with pytest.raises(ValidationError):
            CreateCoursePayload(
                course_id="test-123",
                name="",  # Empty name should fail
                certificate_template_html="<html></html>"
            )
    
    def test_edit_course_payload(self):
        """Test EditCoursePayload with optional fields."""
        payload = EditCoursePayload(
            course_id="test-123",
            name="Updated Course Name"
        )
        assert payload.course_id == "test-123"
        assert payload.name == "Updated Course Name"
        assert payload.certificate_template_html is None
        
        payload_with_template = EditCoursePayload(
            course_id="test-123",
            certificate_template_html="<html><body>New Template</body></html>"
        )
        assert payload_with_template.certificate_template_html == "<html><body>New Template</body></html>"
        assert payload_with_template.name is None


class TestOrganizationModels:
    """Test organization-related models."""
    
    def test_add_organization_payload(self):
        """Test AddOrganizationPayload validation."""
        payload = AddOrganizationPayload(
            website="example.com",
            name="Example Organization",
            sop_email="sop@example.com"
        )
        assert payload.website == "example.com"
        assert payload.name == "Example Organization"
        assert payload.sop_email == "sop@example.com"
    
    def test_add_organization_payload_optional_name(self):
        """Test AddOrganizationPayload with optional name."""
        payload = AddOrganizationPayload(
            website="example.com",
            sop_email="sop@example.com"
        )
        assert payload.website == "example.com"
        assert payload.name is None
        assert payload.sop_email == "sop@example.com"
    
    def test_invalid_email(self):
        """Test invalid email validation."""
        with pytest.raises(ValidationError):
            AddOrganizationPayload(
                website="example.com",
                sop_email="invalid-email"  # Invalid email format
            )


class TestLearnerModels:
    """Test learner-related models."""
    
    def test_learner_csv_row(self):
        """Test LearnerCSVRow validation."""
        row = LearnerCSVRow(
            name="John Doe",
            email="john@example.com",
            organization_website="example.com"
        )
        assert row.name == "John Doe"
        assert row.email == "john@example.com"
        assert row.organization_website == "example.com"
    
    def test_upload_learners_csv_payload(self):
        """Test UploadLearnersCSVPayload validation."""
        payload = UploadLearnersCSVPayload(
            course_id="test-123",
            csv_file_id="file-456",
            uploader="user-789"
        )
        assert payload.course_id == "test-123"
        assert payload.csv_file_id == "file-456"
        assert payload.uploader == "user-789"
    
    def test_csv_validation_result(self):
        """Test CSVValidationResult model."""
        valid_rows = [
            LearnerCSVRow(name="John", email="john@example.com", organization_website="example.com")
        ]
        invalid_rows = [
            {"row_number": 2, "row_data": {}, "errors": ["Missing name"]}
        ]
        duplicate_rows = [
            {"row_number": 3, "row_data": {}, "errors": ["Duplicate email"]}
        ]
        
        result = CSVValidationResult(
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            duplicate_rows=duplicate_rows
        )
        
        assert len(result.valid_rows) == 1
        assert len(result.invalid_rows) == 1
        assert len(result.duplicate_rows) == 1


class TestEnrollmentModels:
    """Test enrollment-related models."""
    
    def test_enrollment_result(self):
        """Test EnrollmentResult model."""
        success_result = EnrollmentResult(
            learner_email="john@example.com",
            success=True,
            enrollment_id="enrollment-123"
        )
        assert success_result.success is True
        assert success_result.enrollment_id == "enrollment-123"
        assert success_result.error is None
        
        failure_result = EnrollmentResult(
            learner_email="jane@example.com",
            success=False,
            error="Enrollment failed"
        )
        assert failure_result.success is False
        assert failure_result.error == "Enrollment failed"
        assert failure_result.enrollment_id is None
    
    def test_upload_result(self):
        """Test UploadResult model."""
        result = UploadResult(
            total_rows=100,
            valid_rows=90,
            invalid_rows=5,
            duplicate_rows=5,
            created_learners=90,
            enrollment_success=85,
            enrollment_failed=5,
            validation_errors=[],
            enrollment_errors=[]
        )
        assert result.total_rows == 100
        assert result.valid_rows == 90
        assert result.created_learners == 90
        assert result.enrollment_success == 85


class TestCertificateModels:
    """Test certificate-related models."""
    
    def test_certificate_context(self):
        """Test CertificateContext model."""
        context = CertificateContext(
            learner_name="John Doe",
            course_name="Python Basics",
            completion_date="2024-01-15T10:30:00Z",
            organization="Example Corp",
            learner_email="john@example.com"
        )
        assert context.learner_name == "John Doe"
        assert context.course_name == "Python Basics"
        assert context.completion_date == "2024-01-15T10:30:00Z"
        assert context.organization == "Example Corp"
        assert context.learner_email == "john@example.com"
    
    def test_certificate_context_validation(self):
        """Test CertificateContext date validation."""
        with pytest.raises(ValidationError):
            CertificateContext(
                learner_name="John Doe",
                course_name="Python Basics",
                completion_date="invalid-date",  # Invalid date format
                organization="Example Corp",
                learner_email="john@example.com"
            )


class TestWebhookModels:
    """Test webhook-related models."""
    
    def test_webhook_payload(self):
        """Test WebhookPayload model."""
        payload = WebhookPayload(
            course_id="test-123",
            email="learner@example.com",
            event_id="event-456",
            completed_at=datetime(2024, 1, 15, 10, 30, 0),
            metadata={"completion_percentage": 100}
        )
        assert payload.course_id == "test-123"
        assert payload.email == "learner@example.com"
        assert payload.event_id == "event-456"
        assert payload.metadata["completion_percentage"] == 100
    
    def test_webhook_payload_optional_fields(self):
        """Test WebhookPayload with optional fields."""
        payload = WebhookPayload(
            course_id="test-123",
            email="learner@example.com"
        )
        assert payload.course_id == "test-123"
        assert payload.email == "learner@example.com"
        assert payload.event_id is None
        assert payload.completed_at is None
        assert payload.metadata is None


class TestSOPModels:
    """Test SOP-related models."""
    
    def test_list_org_learners_payload(self):
        """Test ListOrgLearnersPayload model."""
        payload = ListOrgLearnersPayload(
            organization_website="example.com",
            limit=50,
            offset=0
        )
        assert payload.organization_website == "example.com"
        assert payload.limit == 50
        assert payload.offset == 0
    
    def test_download_certificate_payload(self):
        """Test DownloadCertificatePayload model."""
        payload = DownloadCertificatePayload(
            learner_email="learner@example.com",
            course_id="test-123"
        )
        assert payload.learner_email == "learner@example.com"
        assert payload.course_id == "test-123"


class TestDatabaseModels:
    """Test database models."""
    
    def test_course_model(self):
        """Test CourseModel."""
        now = datetime.utcnow()
        course = CourseModel(
            id="course-123",
            course_id="test-123",
            name="Test Course",
            certificate_template_html="<html></html>",
            created_at=now,
            updated_at=now
        )
        assert course.id == "course-123"
        assert course.course_id == "test-123"
        assert course.name == "Test Course"
    
    def test_organization_model(self):
        """Test OrganizationModel."""
        now = datetime.utcnow()
        org = OrganizationModel(
            id="org-123",
            website="example.com",
            name="Example Corp",
            sop_email="sop@example.com",
            created_at=now,
            updated_at=now
        )
        assert org.id == "org-123"
        assert org.website == "example.com"
        assert org.name == "Example Corp"
        assert org.sop_email == "sop@example.com"
    
    def test_learner_model(self):
        """Test LearnerModel."""
        now = datetime.utcnow()
        learner = LearnerModel(
            id="learner-123",
            name="John Doe",
            email="john@example.com",
            organization_website="example.com",
            course_id="test-123",
            certificate_send_status=CertificateSendStatus.PENDING
        )
        assert learner.id == "learner-123"
        assert learner.name == "John Doe"
        assert learner.email == "john@example.com"
        assert learner.certificate_send_status == CertificateSendStatus.PENDING
    
    def test_webhook_event_model(self):
        """Test WebhookEventModel."""
        now = datetime.utcnow()
        event = WebhookEventModel(
            id="event-123",
            source="graphy",
            payload='{"course_id": "test-123"}',
            course_id="test-123",
            email="learner@example.com",
            event_id="graphy-event-456",
            received_at=now,
            status=WebhookStatus.RECEIVED,
            attempts=0
        )
        assert event.id == "event-123"
        assert event.source == "graphy"
        assert event.status == WebhookStatus.RECEIVED
        assert event.attempts == 0
    
    def test_email_log_model(self):
        """Test EmailLogModel."""
        now = datetime.utcnow()
        log = EmailLogModel(
            id="log-123",
            to_email="sop@example.com",
            subject="Certificate",
            attachment_file_id="file-456",
            status=EmailStatus.SENT,
            response="Message sent successfully",
            created_at=now,
            retry_count=0
        )
        assert log.id == "log-123"
        assert log.to_email == "sop@example.com"
        assert log.status == EmailStatus.SENT
        assert log.retry_count == 0


class TestServiceModels:
    """Test service-related models."""
    
    def test_graphy_enrollment_request(self):
        """Test GraphyEnrollmentRequest."""
        request = GraphyEnrollmentRequest(
            course_id="test-123",
            email="learner@example.com",
            name="John Doe",
            metadata={"organization": "example.com"}
        )
        assert request.course_id == "test-123"
        assert request.email == "learner@example.com"
        assert request.name == "John Doe"
        assert request.metadata["organization"] == "example.com"
    
    def test_graphy_enrollment_response(self):
        """Test GraphyEnrollmentResponse."""
        success_response = GraphyEnrollmentResponse(
            ok=True,
            enrollment_id="enrollment-123"
        )
        assert success_response.ok is True
        assert success_response.enrollment_id == "enrollment-123"
        assert success_response.error is None
        
        failure_response = GraphyEnrollmentResponse(
            ok=False,
            error="Enrollment failed"
        )
        assert failure_response.ok is False
        assert failure_response.error == "Enrollment failed"
        assert failure_response.enrollment_id is None
    
    def test_email_request(self):
        """Test EmailRequest."""
        request = EmailRequest(
            to_email="sop@example.com",
            subject="Certificate",
            body="Please find the certificate attached.",
            attachment_file_id="file-123",
            attachment_filename="certificate.pdf"
        )
        assert request.to_email == "sop@example.com"
        assert request.subject == "Certificate"
        assert request.attachment_file_id == "file-123"
        assert request.attachment_filename == "certificate.pdf"
    
    def test_email_response(self):
        """Test EmailResponse."""
        success_response = EmailResponse(
            ok=True,
            message_id="msg-123"
        )
        assert success_response.ok is True
        assert success_response.message_id == "msg-123"
        assert success_response.error is None
        
        failure_response = EmailResponse(
            ok=False,
            error="Email sending failed"
        )
        assert failure_response.ok is False
        assert failure_response.error == "Email sending failed"
        assert failure_response.message_id is None
    
    def test_pdf_generation_request(self):
        """Test PDFGenerationRequest."""
        request = PDFGenerationRequest(
            html_content="<html><body>Certificate</body></html>",
            filename="certificate.pdf"
        )
        assert "Certificate" in request.html_content
        assert request.filename == "certificate.pdf"
    
    def test_pdf_generation_response(self):
        """Test PDFGenerationResponse."""
        success_response = PDFGenerationResponse(
            ok=True,
            file_id="file-123"
        )
        assert success_response.ok is True
        assert success_response.file_id == "file-123"
        assert success_response.error is None
        
        failure_response = PDFGenerationResponse(
            ok=False,
            error="PDF generation failed"
        )
        assert failure_response.ok is False
        assert failure_response.error == "PDF generation failed"
        assert failure_response.file_id is None


class TestAuthModels:
    """Test authentication-related models."""
    
    def test_auth_context(self):
        """Test AuthContext model."""
        context = AuthContext(
            user_id="user-123",
            role=UserRole.ADMIN
        )
        assert context.user_id == "user-123"
        assert context.role == UserRole.ADMIN
        assert context.organization_website is None
        
        sop_context = AuthContext(
            user_id="sop-456",
            role=UserRole.SOP,
            organization_website="example.com"
        )
        assert sop_context.role == UserRole.SOP
        assert sop_context.organization_website == "example.com"
    
    def test_jwt_payload(self):
        """Test JWTPayload model."""
        now = int(datetime.utcnow().timestamp())
        payload = JWTPayload(
            user_id="user-123",
            role=UserRole.ADMIN,
            exp=now + 3600,
            iat=now
        )
        assert payload.user_id == "user-123"
        assert payload.role == UserRole.ADMIN
        assert payload.exp > payload.iat
        assert payload.organization_website is None
