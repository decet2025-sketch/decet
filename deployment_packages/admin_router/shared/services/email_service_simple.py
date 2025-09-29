"""
Simplified Email service for initial deployment.
"""

import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmailService:
    """Simplified email service for initial deployment."""

    def __init__(self, appwrite_client=None):
        """Initialize email service."""
        self.client = appwrite_client
        logger.info("Email service initialized (simplified mode)")

    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = True) -> Dict[str, Any]:
        """Send email (simplified version)."""
        try:
            logger.info(f"Email prepared for {to_email}: {subject}")
            return {
                "success": True,
                "message_id": "simplified-message-id",
                "message": f"Email prepared for {to_email} (simplified mode)"
            }
        except Exception as e:
            logger.error(f"Email service error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Email service error"
            }

    def send_certificate_email(self, to_email: str, learner_name: str, course_name: str, 
                             certificate_url: str = None) -> Dict[str, Any]:
        """Send certificate email (simplified version)."""
        try:
            subject = f"🎓 Course Completion Certificate - {learner_name}"
            body = f"""
            <html>
            <body>
                <h2>Congratulations {learner_name}!</h2>
                <p>You have successfully completed the course: <strong>{course_name}</strong></p>
                <p>Your certificate is ready for download.</p>
                {f'<p><a href="{certificate_url}">Download Certificate</a></p>' if certificate_url else ''}
                <p>Best regards,<br>Certificate Management System</p>
            </body>
            </html>
            """
            
            return self.send_email(to_email, subject, body, is_html=True)
            
        except Exception as e:
            logger.error(f"Certificate email error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Certificate email error"
            }

    def test_connection(self) -> Dict[str, Any]:
        """Test email service connection."""
        try:
            return {
                "success": True,
                "message": "Email service is configured (simplified mode)",
                "gmail_configured": bool(os.getenv('GMAIL_APP_PASSWORD')),
                "from_email": os.getenv('FROM_EMAIL', 'decet2025@gmail.com')
            }
        except Exception as e:
            logger.error(f"Email service test error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Email service test failed"
            }
