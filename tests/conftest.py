"""
Pytest configuration and fixtures.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'shared'))
sys.path.insert(0, os.path.join(project_root, 'functions', 'admin_router', 'src'))
sys.path.insert(0, os.path.join(project_root, 'functions', 'graphy_webhook', 'src'))
sys.path.insert(0, os.path.join(project_root, 'functions', 'certificate_worker', 'src'))
sys.path.insert(0, os.path.join(project_root, 'functions', 'sop_router', 'src'))


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Mock environment variables for all tests."""
    with patch.dict(os.environ, {
        'APPWRITE_ENDPOINT': 'https://test.appwrite.io/v1',
        'APPWRITE_PROJECT': 'test-project',
        'APPWRITE_API_KEY': 'test-api-key',
        'GRAPHY_API_BASE': 'https://api.graphy.com',
        'GRAPHY_API_KEY': 'test-graphy-key',
        'SENDGRID_API_KEY': 'test-sendgrid-key',
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USER': 'test-user',
        'SMTP_PASS': 'test-pass',
        'HTML_TO_PDF_API_URL': 'https://pdf.test.com/convert',
        'MAX_CSV_ROWS': '5000',
        'CERTIFICATE_BUCKET_ID': 'certificates',
        'MAX_EMAIL_RETRY_ATTEMPTS': '3',
        'EMAIL_RETRY_DELAY': '60'
    }):
        yield


@pytest.fixture
def mock_appwrite_client():
    """Mock Appwrite client for testing."""
    with patch('shared.services.db.Client') as mock_client:
        client = Mock()
        mock_client.return_value = client
        
        # Mock databases service
        client.databases = Mock()
        client.storage = Mock()
        
        yield client


@pytest.fixture
def mock_graphy_service():
    """Mock Graphy service for testing."""
    with patch('shared.services.graphy.requests.Session') as mock_session:
        session = Mock()
        mock_session.return_value = session
        
        yield session


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    with patch('shared.services.email_service.sendgrid.SendGridAPIClient') as mock_sendgrid, \
         patch('shared.services.email_service.smtplib.SMTP') as mock_smtp:
        
        # Mock SendGrid
        mock_sg = Mock()
        mock_sendgrid.return_value = mock_sg
        
        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        yield {
            'sendgrid': mock_sg,
            'smtp': mock_server
        }


@pytest.fixture
def mock_renderer():
    """Mock certificate renderer for testing."""
    with patch('shared.services.renderer.pyppeteer.launch') as mock_launch, \
         patch('shared.services.renderer.requests.post') as mock_post, \
         patch('shared.services.renderer.asyncio.run') as mock_run:
        
        # Mock browser
        mock_browser = Mock()
        mock_page = Mock()
        mock_browser.newPage.return_value = mock_page
        mock_page.pdf.return_value = b"pdf-content"
        mock_launch.return_value = mock_browser
        
        # Mock external API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"pdf-content"
        mock_post.return_value = mock_response
        
        # Mock asyncio
        mock_run.return_value = b"pdf-content"
        
        yield {
            'launch': mock_launch,
            'post': mock_post,
            'run': mock_run
        }


@pytest.fixture
def mock_auth_service():
    """Mock auth service for testing."""
    with patch('shared.services.auth.jwt.decode') as mock_decode:
        yield mock_decode


@pytest.fixture
def sample_course_data():
    """Sample course data for testing."""
    return {
        'id': 'course-123',
        'course_id': 'test-123',
        'name': 'Test Course',
        'certificate_template_html': '<html><body><h1>Certificate</h1><p>{{learner_name}} completed {{course_name}}</p></body></html>',
        'created_at': '2024-01-15T10:30:00Z',
        'updated_at': '2024-01-15T10:30:00Z'
    }


@pytest.fixture
def sample_organization_data():
    """Sample organization data for testing."""
    return {
        'id': 'org-123',
        'website': 'example.com',
        'name': 'Example Corporation',
        'sop_email': 'sop@example.com',
        'created_at': '2024-01-15T10:30:00Z',
        'updated_at': '2024-01-15T10:30:00Z'
    }


@pytest.fixture
def sample_learner_data():
    """Sample learner data for testing."""
    return {
        'id': 'learner-123',
        'name': 'John Doe',
        'email': 'john@example.com',
        'organization_website': 'example.com',
        'course_id': 'test-123',
        'graphy_enrollment_id': 'enrollment-456',
        'enrolled_at': '2024-01-15T10:30:00Z',
        'completion_at': '2024-01-16T10:30:00Z',
        'certificate_generated_at': '2024-01-16T10:35:00Z',
        'certificate_sent_to_sop_at': '2024-01-16T10:40:00Z',
        'certificate_send_status': 'sent',
        'certificate_file_id': 'file-789',
        'last_resend_attempt': None,
        'enrollment_error': None
    }


@pytest.fixture
def sample_webhook_data():
    """Sample webhook data for testing."""
    return {
        'id': 'webhook-123',
        'source': 'graphy',
        'payload': '{"course_id": "test-123", "email": "john@example.com", "event_id": "graphy-event-456"}',
        'course_id': 'test-123',
        'email': 'john@example.com',
        'event_id': 'graphy-event-456',
        'received_at': '2024-01-16T10:30:00Z',
        'processed_at': None,
        'status': 'received',
        'attempts': 0
    }


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """name,email,organization_website
John Doe,john@example.com,example.com
Jane Smith,jane@example.com,example.com
Bob Johnson,bob@example.com,other.com"""


@pytest.fixture
def sample_invalid_csv_content():
    """Sample invalid CSV content for testing."""
    return """name,email,organization_website
John Doe,invalid-email,example.com
,jane@example.com,example.com
Bob Johnson,bob@example.com,"""


@pytest.fixture
def sample_certificate_context():
    """Sample certificate context for testing."""
    from shared.models import CertificateContext
    return CertificateContext(
        learner_name="John Doe",
        course_name="Python Basics",
        completion_date="2024-01-16T10:30:00Z",
        organization="Example Corporation",
        learner_email="john@example.com"
    )


@pytest.fixture
def sample_auth_context_admin():
    """Sample admin auth context for testing."""
    from shared.models import AuthContext, UserRole
    return AuthContext(
        user_id="admin-123",
        role=UserRole.ADMIN
    )


@pytest.fixture
def sample_auth_context_sop():
    """Sample SOP auth context for testing."""
    from shared.models import AuthContext, UserRole
    return AuthContext(
        user_id="sop-456",
        role=UserRole.SOP,
        organization_website="example.com"
    )


@pytest.fixture
def sample_jwt_payload():
    """Sample JWT payload for testing."""
    from shared.models import JWTPayload, UserRole
    import time
    
    now = int(time.time())
    return JWTPayload(
        user_id="user-123",
        role=UserRole.ADMIN,
        exp=now + 3600,
        iat=now
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    for item in items:
        # Add unit marker to all tests by default
        if not any(marker in item.keywords for marker in ["unit", "integration"]):
            item.add_marker(pytest.mark.unit)
