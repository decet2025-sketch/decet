"""
Unit tests for service classes.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from shared.services.db import AppwriteClient
from shared.services.graphy import GraphyService
from shared.services.email_service import EmailService
from shared.services.renderer import CertificateRenderer
from shared.services.auth import AuthService
from shared.models import (
    CourseModel, OrganizationModel, LearnerModel, WebhookEventModel,
    CertificateContext, GraphyEnrollmentRequest, EmailRequest,
    CertificateSendStatus, WebhookStatus, UserRole, AuthContext
)


class TestAppwriteClient:
    """Test AppwriteClient service."""
    
    @pytest.fixture
    def mock_appwrite_client(self):
        """Mock Appwrite client."""
        with patch('shared.services.db.Client') as mock_client:
            client = Mock()
            mock_client.return_value = client
            
            # Mock databases service
            client.databases = Mock()
            client.storage = Mock()
            
            yield client
    
    @pytest.fixture
    def db_client(self, mock_appwrite_client):
        """Create AppwriteClient instance with mocked dependencies."""
        return AppwriteClient(
            endpoint="https://test.appwrite.io/v1",
            project_id="test-project",
            api_key="test-key"
        )
    
    def test_get_course_by_course_id_success(self, db_client, mock_appwrite_client):
        """Test successful course retrieval."""
        # Mock database response
        mock_appwrite_client.databases.list_documents.return_value = {
            'documents': [{
                '$id': 'course-123',
                'course_id': 'test-123',
                'name': 'Test Course',
                'certificate_template_html': '<html></html>',
                'created_at': '2024-01-15T10:30:00Z',
                'updated_at': '2024-01-15T10:30:00Z'
            }]
        }
        
        course = db_client.get_course_by_course_id('test-123')
        
        assert course is not None
        assert course.course_id == 'test-123'
        assert course.name == 'Test Course'
        mock_appwrite_client.databases.list_documents.assert_called_once()
    
    def test_get_course_by_course_id_not_found(self, db_client, mock_appwrite_client):
        """Test course not found."""
        mock_appwrite_client.databases.list_documents.return_value = {
            'documents': []
        }
        
        course = db_client.get_course_by_course_id('nonexistent')
        
        assert course is None
    
    def test_create_course_success(self, db_client, mock_appwrite_client):
        """Test successful course creation."""
        mock_appwrite_client.databases.create_document.return_value = {
            '$id': 'course-123',
            'course_id': 'test-123',
            'name': 'Test Course',
            'certificate_template_html': '<html></html>',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z'
        }
        
        course_data = {
            'course_id': 'test-123',
            'name': 'Test Course',
            'certificate_template_html': '<html></html>'
        }
        
        course = db_client.create_course(course_data)
        
        assert course is not None
        assert course.course_id == 'test-123'
        mock_appwrite_client.databases.create_document.assert_called_once()
    
    def test_create_learner_if_not_exists_new(self, db_client, mock_appwrite_client):
        """Test creating new learner."""
        # Mock no existing learner
        mock_appwrite_client.databases.list_documents.return_value = {
            'documents': []
        }
        
        # Mock successful creation
        mock_appwrite_client.databases.create_document.return_value = {
            '$id': 'learner-123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'organization_website': 'example.com',
            'course_id': 'test-123',
            'certificate_send_status': 'pending'
        }
        
        learner_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'organization_website': 'example.com',
            'course_id': 'test-123'
        }
        
        learner = db_client.create_learner_if_not_exists(learner_data)
        
        assert learner is not None
        assert learner.name == 'John Doe'
        assert learner.email == 'john@example.com'
    
    def test_create_learner_if_not_exists_existing(self, db_client, mock_appwrite_client):
        """Test creating learner when already exists."""
        # Mock existing learner
        mock_appwrite_client.databases.list_documents.return_value = {
            'documents': [{
                '$id': 'learner-123',
                'name': 'John Doe',
                'email': 'john@example.com',
                'organization_website': 'example.com',
                'course_id': 'test-123',
                'certificate_send_status': 'pending'
            }]
        }
        
        learner_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'organization_website': 'example.com',
            'course_id': 'test-123'
        }
        
        learner = db_client.create_learner_if_not_exists(learner_data)
        
        assert learner is not None
        assert learner.name == 'John Doe'
        # Should not call create_document
        mock_appwrite_client.databases.create_document.assert_not_called()


class TestGraphyService:
    """Test GraphyService."""
    
    @pytest.fixture
    def graphy_service(self):
        """Create GraphyService instance."""
        return GraphyService(
            api_base="https://api.graphy.com",
            api_key="test-key"
        )
    
    @patch('shared.services.graphy.requests.Session.post')
    def test_enroll_learner_success(self, mock_post, graphy_service):
        """Test successful learner enrollment."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'enrollment_id': 'enrollment-123',
            'status': 'enrolled'
        }
        mock_post.return_value = mock_response
        
        request = GraphyEnrollmentRequest(
            course_id="test-123",
            email="learner@example.com",
            name="John Doe"
        )
        
        response = graphy_service.enroll_learner(request)
        
        assert response.ok is True
        assert response.enrollment_id == 'enrollment-123'
        assert response.error is None
    
    @patch('shared.services.graphy.requests.Session.post')
    def test_enroll_learner_failure(self, mock_post, graphy_service):
        """Test failed learner enrollment."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'Course not found'
        }
        mock_post.return_value = mock_response
        
        request = GraphyEnrollmentRequest(
            course_id="nonexistent",
            email="learner@example.com",
            name="John Doe"
        )
        
        response = graphy_service.enroll_learner(request)
        
        assert response.ok is False
        assert response.error == 'Course not found'
        assert response.enrollment_id is None
    
    @patch('shared.services.graphy.requests.Session.post')
    def test_enroll_learner_network_error(self, mock_post, graphy_service):
        """Test network error during enrollment."""
        # Mock network error
        mock_post.side_effect = Exception("Network error")
        
        request = GraphyEnrollmentRequest(
            course_id="test-123",
            email="learner@example.com",
            name="John Doe"
        )
        
        response = graphy_service.enroll_learner(request)
        
        assert response.ok is False
        assert "Network error" in response.error
    
    def test_verify_webhook_signature_valid(self, graphy_service):
        """Test valid webhook signature verification."""
        payload = '{"course_id": "test-123", "email": "learner@example.com"}'
        secret = "test-secret"
        
        # Generate expected signature
        import hmac
        import hashlib
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        is_valid = graphy_service.verify_webhook_signature(payload, expected_signature, secret)
        
        assert is_valid is True
    
    def test_verify_webhook_signature_invalid(self, graphy_service):
        """Test invalid webhook signature verification."""
        payload = '{"course_id": "test-123", "email": "learner@example.com"}'
        secret = "test-secret"
        invalid_signature = "invalid-signature"
        
        is_valid = graphy_service.verify_webhook_signature(payload, invalid_signature, secret)
        
        assert is_valid is False


class TestEmailService:
    """Test EmailService."""
    
    @pytest.fixture
    def email_service_sendgrid(self):
        """Create EmailService with SendGrid."""
        return EmailService(sendgrid_api_key="test-sendgrid-key")
    
    @pytest.fixture
    def email_service_smtp(self):
        """Create EmailService with SMTP."""
        return EmailService(smtp_config={
            'host': 'smtp.example.com',
            'port': 587,
            'username': 'user',
            'password': 'pass',
            'use_tls': True
        })
    
    @patch('shared.services.email_service.sendgrid.SendGridAPIClient')
    def test_send_email_sendgrid_success(self, mock_sendgrid, email_service_sendgrid):
        """Test successful email sending via SendGrid."""
        # Mock SendGrid response
        mock_sg = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.headers = {'X-Message-Id': 'msg-123'}
        mock_sg.send.return_value = mock_response
        mock_sendgrid.return_value = mock_sg
        
        request = EmailRequest(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        response = email_service_sendgrid.send_email(request)
        
        assert response.ok is True
        assert response.message_id == 'msg-123'
        assert response.error is None
    
    @patch('shared.services.email_service.smtplib.SMTP')
    def test_send_email_smtp_success(self, mock_smtp, email_service_smtp):
        """Test successful email sending via SMTP."""
        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        request = EmailRequest(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        response = email_service_smtp.send_email(request)
        
        assert response.ok is True
        assert response.message_id == "smtp-sent"
        assert response.error is None
    
    def test_send_certificate_email(self, email_service_sendgrid):
        """Test certificate email sending."""
        with patch.object(email_service_sendgrid, 'send_email') as mock_send:
            mock_send.return_value = Mock(ok=True, message_id='msg-123')
            
            response = email_service_sendgrid.send_certificate_email(
                to_email="sop@example.com",
                learner_name="John Doe",
                learner_email="john@example.com",
                course_name="Python Basics",
                organization_name="Example Corp",
                attachment_content=b"pdf-content",
                attachment_filename="certificate.pdf"
            )
            
            assert response.ok is True
            assert response.message_id == 'msg-123'
            mock_send.assert_called_once()


class TestCertificateRenderer:
    """Test CertificateRenderer service."""
    
    @pytest.fixture
    def renderer(self):
        """Create CertificateRenderer instance."""
        return CertificateRenderer()
    
    def test_sanitize_template_removes_scripts(self, renderer):
        """Test template sanitization removes script tags."""
        html_template = """
        <html>
        <head>
            <script>alert('xss')</script>
        </head>
        <body>
            <h1>Certificate</h1>
        </body>
        </html>
        """
        
        sanitized = renderer.sanitize_template(html_template)
        
        assert '<script>' not in sanitized
        assert 'alert' not in sanitized
        assert '<h1>Certificate</h1>' in sanitized
    
    def test_sanitize_template_removes_external_resources(self, renderer):
        """Test template sanitization removes external resources."""
        html_template = """
        <html>
        <head>
            <link rel="stylesheet" href="https://external.com/style.css">
            <img src="https://external.com/image.jpg">
        </head>
        <body>
            <h1>Certificate</h1>
        </body>
        </html>
        """
        
        sanitized = renderer.sanitize_template(html_template)
        
        assert 'https://external.com' not in sanitized
        assert '<h1>Certificate</h1>' in sanitized
    
    def test_render_certificate_success(self, renderer):
        """Test successful certificate rendering."""
        template_html = """
        <html>
        <body>
            <h1>Certificate of Completion</h1>
            <p>This certifies that {{learner_name}} has completed {{course_name}}</p>
            <p>Organization: {{organization}}</p>
            <p>Date: {{completion_date}}</p>
        </body>
        </html>
        """
        
        context = CertificateContext(
            learner_name="John Doe",
            course_name="Python Basics",
            completion_date="2024-01-15T10:30:00Z",
            organization="Example Corp",
            learner_email="john@example.com"
        )
        
        rendered = renderer.render_certificate(template_html, context)
        
        assert "John Doe" in rendered
        assert "Python Basics" in rendered
        assert "Example Corp" in rendered
        assert "2024-01-15T10:30:00Z" in rendered
    
    def test_render_certificate_missing_variables(self, renderer):
        """Test certificate rendering with missing template variables."""
        template_html = """
        <html>
        <body>
            <h1>Certificate</h1>
            <p>{{learner_name}} - {{course_name}}</p>
            <p>Custom: {{custom_field}}</p>
        </body>
        </html>
        """
        
        context = CertificateContext(
            learner_name="John Doe",
            course_name="Python Basics",
            completion_date="2024-01-15T10:30:00Z",
            organization="Example Corp",
            learner_email="john@example.com"
        )
        
        rendered = renderer.render_certificate(template_html, context)
        
        assert "John Doe" in rendered
        assert "Python Basics" in rendered
        # Missing custom_field should be empty
        assert "Custom: " in rendered
    
    @patch('shared.services.renderer.pyppeteer.launch')
    def test_html_to_pdf_pyppeteer_success(self, mock_launch, renderer):
        """Test successful PDF generation with pyppeteer."""
        # Mock browser and page
        mock_browser = Mock()
        mock_page = Mock()
        mock_browser.newPage.return_value = mock_page
        mock_page.pdf.return_value = b"pdf-content"
        mock_launch.return_value = mock_browser
        
        html_content = "<html><body>Certificate</body></html>"
        
        # This would need to be run in an async context in real usage
        # For testing, we'll mock the asyncio.run call
        with patch('shared.services.renderer.asyncio.run') as mock_run:
            mock_run.return_value = b"pdf-content"
            
            pdf_response = renderer.html_to_pdf(html_content, "certificate.pdf")
            
            assert pdf_response.ok is True
            assert pdf_response.file_id == "pdf_generated"
    
    @patch('shared.services.renderer.requests.post')
    def test_html_to_pdf_external_api_success(self, mock_post, renderer):
        """Test successful PDF generation with external API."""
        # Mock external API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"pdf-content"
        mock_post.return_value = mock_response
        
        # Set external API URL
        renderer.html_to_pdf_api_url = "https://pdf-api.com/convert"
        
        html_content = "<html><body>Certificate</body></html>"
        
        # Mock pyppeteer failure
        with patch('shared.services.renderer.asyncio.run') as mock_run:
            mock_run.side_effect = Exception("Pyppeteer failed")
            
            pdf_response = renderer.html_to_pdf(html_content, "certificate.pdf")
            
            assert pdf_response.ok is True
            assert pdf_response.file_id == "pdf_generated"
            mock_post.assert_called_once()


class TestAuthService:
    """Test AuthService."""
    
    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance."""
        return AuthService(jwt_secret="test-secret")
    
    @patch('shared.services.auth.jwt.decode')
    def test_validate_appwrite_jwt_success(self, mock_decode, auth_service):
        """Test successful JWT validation."""
        mock_decode.return_value = {
            'user_id': 'user-123',
            'role': 'admin',
            'exp': 1234567890,
            'iat': 1234567890
        }
        
        context = auth_service.validate_appwrite_jwt("valid-token")
        
        assert context is not None
        assert context.user_id == 'user-123'
        assert context.role == UserRole.ADMIN
        assert context.organization_website is None
    
    @patch('shared.services.auth.jwt.decode')
    def test_validate_appwrite_jwt_sop_role(self, mock_decode, auth_service):
        """Test JWT validation with SOP role."""
        mock_decode.return_value = {
            'user_id': 'sop-456',
            'role': 'sop',
            'organization_website': 'example.com',
            'exp': 1234567890,
            'iat': 1234567890
        }
        
        context = auth_service.validate_appwrite_jwt("valid-token")
        
        assert context is not None
        assert context.user_id == 'sop-456'
        assert context.role == UserRole.SOP
        assert context.organization_website == 'example.com'
    
    @patch('shared.services.auth.jwt.decode')
    def test_validate_appwrite_jwt_expired(self, mock_decode, auth_service):
        """Test JWT validation with expired token."""
        from jwt.exceptions import ExpiredSignatureError
        mock_decode.side_effect = ExpiredSignatureError("Token expired")
        
        context = auth_service.validate_appwrite_jwt("expired-token")
        
        assert context is None
    
    @patch('shared.services.auth.jwt.decode')
    def test_validate_appwrite_jwt_invalid(self, mock_decode, auth_service):
        """Test JWT validation with invalid token."""
        from jwt.exceptions import InvalidTokenError
        mock_decode.side_effect = InvalidTokenError("Invalid token")
        
        context = auth_service.validate_appwrite_jwt("invalid-token")
        
        assert context is None
    
    def test_validate_token_auth_success(self, auth_service):
        """Test successful token-based auth."""
        # Enable token auth
        auth_service.allow_token_auth = True
        auth_service.dev_tokens = {'admin': 'dev-admin-token'}
        
        context = auth_service.validate_token_auth('dev-admin-token')
        
        assert context is not None
        assert context.user_id == 'dev-admin'
        assert context.role == UserRole.ADMIN
    
    def test_validate_token_auth_disabled(self, auth_service):
        """Test token auth when disabled."""
        auth_service.allow_token_auth = False
        
        context = auth_service.validate_token_auth('any-token')
        
        assert context is None
    
    def test_require_admin(self, auth_service):
        """Test admin role requirement."""
        admin_context = AuthContext(user_id="user-123", role=UserRole.ADMIN)
        sop_context = AuthContext(user_id="sop-456", role=UserRole.SOP)
        
        assert auth_service.require_admin(admin_context) is True
        assert auth_service.require_admin(sop_context) is False
        assert auth_service.require_admin(None) is False
    
    def test_require_sop(self, auth_service):
        """Test SOP role requirement."""
        admin_context = AuthContext(user_id="user-123", role=UserRole.ADMIN)
        sop_context = AuthContext(user_id="sop-456", role=UserRole.SOP)
        
        assert auth_service.require_sop(admin_context) is False
        assert auth_service.require_sop(sop_context) is True
        assert auth_service.require_sop(None) is False
    
    def test_can_access_organization_admin(self, auth_service):
        """Test organization access for admin users."""
        admin_context = AuthContext(user_id="user-123", role=UserRole.ADMIN)
        
        assert auth_service.can_access_organization(admin_context, "any-org.com") is True
    
    def test_can_access_organization_sop_same_org(self, auth_service):
        """Test organization access for SOP users with same organization."""
        sop_context = AuthContext(
            user_id="sop-456",
            role=UserRole.SOP,
            organization_website="example.com"
        )
        
        assert auth_service.can_access_organization(sop_context, "example.com") is True
    
    def test_can_access_organization_sop_different_org(self, auth_service):
        """Test organization access for SOP users with different organization."""
        sop_context = AuthContext(
            user_id="sop-456",
            role=UserRole.SOP,
            organization_website="example.com"
        )
        
        assert auth_service.can_access_organization(sop_context, "other.com") is False
    
    def test_validate_request_auth_bearer_token(self, auth_service):
        """Test request auth validation with Bearer token."""
        headers = {'Authorization': 'Bearer valid-token'}
        
        with patch.object(auth_service, 'validate_appwrite_jwt') as mock_validate:
            mock_validate.return_value = AuthContext(user_id="user-123", role=UserRole.ADMIN)
            
            context = auth_service.validate_request_auth(headers)
            
            assert context is not None
            assert context.user_id == "user-123"
            mock_validate.assert_called_once_with("valid-token")
    
    def test_validate_request_auth_x_appwrite_jwt(self, auth_service):
        """Test request auth validation with X-Appwrite-JWT header."""
        headers = {'X-Appwrite-JWT': 'jwt-token'}
        
        with patch.object(auth_service, 'validate_appwrite_jwt') as mock_validate:
            mock_validate.return_value = AuthContext(user_id="user-123", role=UserRole.ADMIN)
            
            context = auth_service.validate_request_auth(headers)
            
            assert context is not None
            assert context.user_id == "user-123"
            mock_validate.assert_called_once_with("jwt-token")
    
    def test_validate_request_auth_x_auth_token(self, auth_service):
        """Test request auth validation with X-Auth-Token header."""
        headers = {'X-Auth-Token': 'dev-token'}
        
        with patch.object(auth_service, 'validate_token_auth') as mock_validate:
            mock_validate.return_value = AuthContext(user_id="dev-user", role=UserRole.ADMIN)
            
            context = auth_service.validate_request_auth(headers)
            
            assert context is not None
            assert context.user_id == "dev-user"
            mock_validate.assert_called_once_with("dev-token")
