"""
Unit tests for Appwrite functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

# Import function modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functions', 'admin_router', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functions', 'graphy_webhook', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functions', 'certificate_worker', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functions', 'sop_router', 'src'))

from shared.models import (
    ActionType, SOPActionType, UserRole, AuthContext,
    CreateCoursePayload, UploadLearnersCSVPayload, WebhookPayload
)


class TestAdminRouter:
    """Test AdminRouter function."""
    
    @pytest.fixture
    def mock_request(self):
        """Mock Appwrite request object."""
        request = Mock()
        request.json.return_value = {
            "action": "CREATE_COURSE",
            "payload": {
                "course_id": "test-123",
                "name": "Test Course",
                "certificate_template_html": "<html></html>"
            }
        }
        request.headers = {
            "Authorization": "Bearer valid-token"
        }
        return request
    
    @pytest.fixture
    def admin_router(self):
        """Create AdminRouter instance with mocked dependencies."""
        with patch('main.AppwriteClient') as mock_db, \
             patch('main.GraphyService') as mock_graphy, \
             patch('main.EmailService') as mock_email, \
             patch('main.CertificateRenderer') as mock_renderer, \
             patch('main.AuthService') as mock_auth:
            
            # Mock auth context
            mock_auth.return_value.validate_request_auth.return_value = AuthContext(
                user_id="admin-123",
                role=UserRole.ADMIN
            )
            
            from main import AdminRouter
            return AdminRouter()
    
    def test_handle_create_course_success(self, admin_router, mock_request):
        """Test successful course creation."""
        # Mock database operations
        admin_router.db.get_course_by_course_id.return_value = None  # Course doesn't exist
        admin_router.db.create_course.return_value = Mock(
            id="course-123",
            course_id="test-123",
            name="Test Course",
            certificate_template_html="<html></html>",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Mock request data
        request_data = {
            "action": "CREATE_COURSE",
            "payload": {
                "course_id": "test-123",
                "name": "Test Course",
                "certificate_template_html": "<html></html>"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = admin_router.handle_request(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 201
        assert 'course' in response['data']
        admin_router.db.create_course.assert_called_once()
    
    def test_handle_create_course_already_exists(self, admin_router, mock_request):
        """Test course creation when course already exists."""
        # Mock existing course
        admin_router.db.get_course_by_course_id.return_value = Mock(
            course_id="test-123",
            name="Existing Course"
        )
        
        request_data = {
            "action": "CREATE_COURSE",
            "payload": {
                "course_id": "test-123",
                "name": "Test Course",
                "certificate_template_html": "<html></html>"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = admin_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 409
        assert response['error']['code'] == 'COURSE_EXISTS'
        admin_router.db.create_course.assert_not_called()
    
    def test_handle_upload_learners_csv_success(self, admin_router, mock_request):
        """Test successful CSV upload."""
        # Mock course exists
        admin_router.db.get_course_by_course_id.return_value = Mock(
            course_id="test-123",
            name="Test Course"
        )
        
        # Mock CSV content
        admin_router.db.get_file_content.return_value = b"name,email,organization_website\nJohn Doe,john@example.com,example.com"
        
        # Mock organization exists
        admin_router.db.get_organization_by_website.return_value = Mock(
            website="example.com",
            name="Example Corp"
        )
        
        # Mock learner creation
        admin_router.db.create_learner_if_not_exists.return_value = Mock(
            id="learner-123",
            name="John Doe",
            email="john@example.com"
        )
        
        # Mock Graphy enrollment
        admin_router.graphy.enroll_learner.return_value = Mock(
            ok=True,
            enrollment_id="enrollment-123"
        )
        
        request_data = {
            "action": "UPLOAD_LEARNERS_CSV",
            "payload": {
                "course_id": "test-123",
                "csv_file_id": "file-456",
                "uploader": "admin-123"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = admin_router.handle_request(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'data' in response
        admin_router.db.get_file_content.assert_called_once()
    
    def test_handle_upload_learners_csv_course_not_found(self, admin_router, mock_request):
        """Test CSV upload when course doesn't exist."""
        # Mock course doesn't exist
        admin_router.db.get_course_by_course_id.return_value = None
        
        request_data = {
            "action": "UPLOAD_LEARNERS_CSV",
            "payload": {
                "course_id": "nonexistent",
                "csv_file_id": "file-456",
                "uploader": "admin-123"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = admin_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 404
        assert response['error']['code'] == 'COURSE_NOT_FOUND'
    
    def test_handle_unauthorized_request(self, admin_router, mock_request):
        """Test unauthorized request handling."""
        # Mock no auth context
        admin_router.auth.validate_request_auth.return_value = None
        
        request_data = {
            "action": "CREATE_COURSE",
            "payload": {
                "course_id": "test-123",
                "name": "Test Course",
                "certificate_template_html": "<html></html>"
            }
        }
        
        headers = {"Authorization": "Bearer invalid-token"}
        
        response = admin_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 401
        assert response['error']['code'] == 'AUTH_ERROR'


class TestGraphyWebhookHandler:
    """Test GraphyWebhookHandler function."""
    
    @pytest.fixture
    def webhook_handler(self):
        """Create GraphyWebhookHandler instance with mocked dependencies."""
        with patch('main.AppwriteClient') as mock_db, \
             patch('main.GraphyService') as mock_graphy:
            
            from main import GraphyWebhookHandler
            return GraphyWebhookHandler()
    
    def test_handle_webhook_success(self, webhook_handler):
        """Test successful webhook handling."""
        # Mock webhook event creation
        webhook_handler.db.create_webhook_event.return_value = Mock(
            id="webhook-123",
            status="received"
        )
        
        # Mock enqueue function
        webhook_handler._enqueue_certificate_worker = Mock()
        
        request_data = {
            "course_id": "test-123",
            "email": "learner@example.com",
            "event_id": "graphy-event-456"
        }
        
        headers = {}
        
        response = webhook_handler.handle_webhook(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'event_id' in response['data']
        webhook_handler.db.create_webhook_event.assert_called_once()
    
    def test_handle_webhook_duplicate_event(self, webhook_handler):
        """Test webhook handling with duplicate event."""
        # Mock existing processed event
        webhook_handler.db.databases.list_documents.return_value = {
            'documents': [{
                'event_id': 'graphy-event-456',
                'status': 'processed'
            }]
        }
        
        request_data = {
            "course_id": "test-123",
            "email": "learner@example.com",
            "event_id": "graphy-event-456"
        }
        
        headers = {}
        
        response = webhook_handler.handle_webhook(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert response['data']['message'] == 'Webhook already processed'
    
    def test_handle_webhook_invalid_payload(self, webhook_handler):
        """Test webhook handling with invalid payload."""
        request_data = {
            "course_id": "test-123",
            # Missing required email field
        }
        
        headers = {}
        
        response = webhook_handler.handle_webhook(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 400
        assert response['error']['code'] == 'INVALID_PAYLOAD'
    
    def test_handle_webhook_signature_verification_failed(self, webhook_handler):
        """Test webhook handling with failed signature verification."""
        # Mock signature verification failure
        webhook_handler.graphy.verify_webhook_signature.return_value = False
        
        request_data = {
            "course_id": "test-123",
            "email": "learner@example.com"
        }
        
        headers = {"X-Graphy-Signature": "invalid-signature"}
        
        response = webhook_handler.handle_webhook(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 401
        assert response['error']['code'] == 'INVALID_SIGNATURE'


class TestCertificateWorker:
    """Test CertificateWorker function."""
    
    @pytest.fixture
    def certificate_worker(self):
        """Create CertificateWorker instance with mocked dependencies."""
        with patch('main.AppwriteClient') as mock_db, \
             patch('main.EmailService') as mock_email, \
             patch('main.CertificateRenderer') as mock_renderer:
            
            from main import CertificateWorker
            return CertificateWorker()
    
    def test_process_webhook_event_success(self, certificate_worker):
        """Test successful webhook event processing."""
        # Mock webhook event
        webhook_event = Mock(
            id="webhook-123",
            status="received",
            attempts=0,
            payload='{"course_id": "test-123", "email": "learner@example.com"}',
            course_id="test-123",
            email="learner@example.com"
        )
        
        certificate_worker.db.get_webhook_event.return_value = webhook_event
        certificate_worker.db.update_webhook_event.return_value = webhook_event
        
        # Mock learner
        certificate_worker.db.get_learner_by_course_and_email.return_value = Mock(
            id="learner-123",
            name="John Doe",
            email="learner@example.com",
            organization_website="example.com",
            completion_at=None
        )
        
        # Mock course
        certificate_worker.db.get_course_by_course_id.return_value = Mock(
            course_id="test-123",
            name="Test Course",
            certificate_template_html="<html></html>"
        )
        
        # Mock organization
        certificate_worker.db.get_organization_by_website.return_value = Mock(
            website="example.com",
            name="Example Corp",
            sop_email="sop@example.com"
        )
        
        # Mock PDF generation
        certificate_worker._generate_certificate_pdf.return_value = {
            'ok': True,
            'file_id': 'file-123'
        }
        
        # Mock email sending
        certificate_worker._send_certificate_email.return_value = {
            'ok': True,
            'message_id': 'msg-123'
        }
        
        response = certificate_worker.process_webhook_event("webhook-123")
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'learner_email' in response['data']
    
    def test_process_webhook_event_webhook_not_found(self, certificate_worker):
        """Test webhook event processing when webhook not found."""
        certificate_worker.db.get_webhook_event.return_value = None
        
        response = certificate_worker.process_webhook_event("nonexistent")
        
        assert response['ok'] is False
        assert response['status'] == 404
        assert response['error']['code'] == 'WEBHOOK_NOT_FOUND'
    
    def test_process_webhook_event_already_processed(self, certificate_worker):
        """Test webhook event processing when already processed."""
        webhook_event = Mock(
            id="webhook-123",
            status="processed",
            attempts=1
        )
        
        certificate_worker.db.get_webhook_event.return_value = webhook_event
        
        response = certificate_worker.process_webhook_event("webhook-123")
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert response['data']['message'] == 'Webhook event already processed'
    
    def test_process_webhook_event_learner_not_found(self, certificate_worker):
        """Test webhook event processing when learner not found."""
        webhook_event = Mock(
            id="webhook-123",
            status="received",
            attempts=0,
            payload='{"course_id": "test-123", "email": "learner@example.com"}',
            course_id="test-123",
            email="learner@example.com"
        )
        
        certificate_worker.db.get_webhook_event.return_value = webhook_event
        certificate_worker.db.update_webhook_event.return_value = webhook_event
        certificate_worker.db.get_learner_by_course_and_email.return_value = None
        
        response = certificate_worker.process_webhook_event("webhook-123")
        
        assert response['ok'] is False
        assert response['status'] == 404
        assert response['error']['code'] == 'LEARNER_NOT_FOUND'


class TestSOPRouter:
    """Test SOPRouter function."""
    
    @pytest.fixture
    def sop_router(self):
        """Create SOPRouter instance with mocked dependencies."""
        with patch('main.AppwriteClient') as mock_db, \
             patch('main.EmailService') as mock_email, \
             patch('main.AuthService') as mock_auth:
            
            # Mock auth context
            mock_auth.return_value.validate_request_auth.return_value = AuthContext(
                user_id="sop-123",
                role=UserRole.SOP,
                organization_website="example.com"
            )
            
            from main import SOPRouter
            return SOPRouter()
    
    def test_handle_list_org_learners_success(self, sop_router):
        """Test successful organization learners listing."""
        # Mock learners
        mock_learners = [
            Mock(
                id="learner-123",
                name="John Doe",
                email="john@example.com",
                organization_website="example.com",
                course_id="test-123",
                dict=Mock(return_value={
                    "id": "learner-123",
                    "name": "John Doe",
                    "email": "john@example.com"
                })
            )
        ]
        
        sop_router.db.query_learners_for_org.return_value = mock_learners
        
        request_data = {
            "action": "LIST_ORG_LEARNERS",
            "payload": {
                "organization_website": "example.com",
                "limit": 50,
                "offset": 0
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'learners' in response['data']
        assert len(response['data']['learners']) == 1
        sop_router.db.query_learners_for_org.assert_called_once()
    
    def test_handle_list_org_learners_access_denied(self, sop_router):
        """Test organization learners listing with access denied."""
        # Mock auth context for different organization
        sop_router.auth.validate_request_auth.return_value = AuthContext(
            user_id="sop-456",
            role=UserRole.SOP,
            organization_website="other.com"
        )
        
        request_data = {
            "action": "LIST_ORG_LEARNERS",
            "payload": {
                "organization_website": "example.com",  # Different org
                "limit": 50,
                "offset": 0
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 403
        assert response['error']['code'] == 'AUTH_ERROR'
    
    def test_handle_download_certificate_success(self, sop_router):
        """Test successful certificate download."""
        # Mock learner
        mock_learner = Mock(
            id="learner-123",
            name="John Doe",
            email="learner@example.com",
            organization_website="example.com",
            certificate_file_id="file-123",
            certificate_generated_at=datetime.utcnow()
        )
        
        sop_router.db.get_learner_by_course_and_email.return_value = mock_learner
        sop_router.db.get_file_download_url.return_value = "https://download-url.com/file-123"
        
        request_data = {
            "action": "DOWNLOAD_CERTIFICATE",
            "payload": {
                "learner_email": "learner@example.com",
                "course_id": "test-123"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'download_url' in response['data']
        assert response['data']['download_url'] == "https://download-url.com/file-123"
    
    def test_handle_download_certificate_not_found(self, sop_router):
        """Test certificate download when learner not found."""
        sop_router.db.get_learner_by_course_and_email.return_value = None
        
        request_data = {
            "action": "DOWNLOAD_CERTIFICATE",
            "payload": {
                "learner_email": "nonexistent@example.com",
                "course_id": "test-123"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 404
        assert response['error']['code'] == 'LEARNER_NOT_FOUND'
    
    def test_handle_resend_certificate_success(self, sop_router):
        """Test successful certificate resend request."""
        # Mock learner
        mock_learner = Mock(
            id="learner-123",
            name="John Doe",
            email="learner@example.com",
            organization_website="example.com",
            completion_at=datetime.utcnow(),
            certificate_send_status="sent"
        )
        
        sop_router.db.get_learner_by_course_and_email.return_value = mock_learner
        sop_router.db.update_learner.return_value = mock_learner
        
        request_data = {
            "action": "RESEND_CERTIFICATE",
            "payload": {
                "learner_email": "learner@example.com",
                "course_id": "test-123"
            }
        }
        
        headers = {"Authorization": "Bearer valid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is True
        assert response['status'] == 200
        assert 'learner_email' in response['data']
        sop_router.db.update_learner.assert_called_once()
    
    def test_handle_unauthorized_request(self, sop_router):
        """Test unauthorized request handling."""
        # Mock no auth context
        sop_router.auth.validate_request_auth.return_value = None
        
        request_data = {
            "action": "LIST_ORG_LEARNERS",
            "payload": {
                "organization_website": "example.com"
            }
        }
        
        headers = {"Authorization": "Bearer invalid-token"}
        
        response = sop_router.handle_request(request_data, headers)
        
        assert response['ok'] is False
        assert response['status'] == 401
        assert response['error']['code'] == 'AUTH_ERROR'
