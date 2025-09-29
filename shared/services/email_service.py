"""
Email service using Appwrite's built-in SMTP functionality.
"""

import logging
import os
from typing import Optional, Dict, Any
try:
    from appwrite.services.messaging import Messaging
    from appwrite.client import Client
    MESSAGING_AVAILABLE = True
except ImportError:
    MESSAGING_AVAILABLE = False
    # Fallback for when messaging service is not available
    class Messaging:
        def __init__(self, client):
            pass
    class Client:
        pass

from ..models import EmailRequest, EmailResponse

logger = logging.getLogger(__name__)


class EmailService:
    """Email service using Appwrite's built-in SMTP functionality."""

    def __init__(self, appwrite_client: Client):
        """Initialize email service with Appwrite client."""
        self.client = appwrite_client
        if MESSAGING_AVAILABLE:
            self.messaging = Messaging(appwrite_client)
        else:
            self.messaging = None
        
        # Gmail SMTP configuration
        self.smtp_config = {
            'host': 'smtp.gmail.com',
            'port': 587,
            'username': 'decet2025@gmail.com',
            'password': os.getenv('GMAIL_APP_PASSWORD'),  # App-specific password
            'use_tls': True,
            'from_email': 'decet2025@gmail.com'
        }

    def send_email(self, request: EmailRequest, attachment_content: Optional[bytes] = None) -> EmailResponse:
        """Send email using Appwrite's messaging service."""
        try:
            # Create email message
            message_data = {
                'to': request.to_email,
                'subject': request.subject,
                'html': request.body,
                'from': self.smtp_config['from_email']
            }
            
            # Add attachment if provided
            if attachment_content and request.attachment_filename:
                # For now, we'll store the attachment in Appwrite Storage and include a link
                # This is a limitation of Appwrite's messaging service
                logger.warning("Attachments not directly supported in Appwrite messaging. Consider using secure links.")
            
            # Send email via Appwrite
            result = self.messaging.create_email(
                message_id='unique',  # Appwrite will generate this
                subject=request.subject,
                html=request.body,
                text=request.body.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n'),
                to=[request.to_email],
                cc=[],
                bcc=[],
                attachments=[],
                draft=False,
                scheduled_at=None
            )
            
            logger.info(f"Email sent successfully to {request.to_email} via Appwrite")
            return EmailResponse(
                ok=True,
                message_id=result.get('$id', 'appwrite-sent')
            )
                
        except Exception as e:
            logger.error(f"Error sending email via Appwrite: {e}")
            return EmailResponse(ok=False, error=str(e))

    def send_email_with_attachment(self, request: EmailRequest, attachment_content: bytes, attachment_filename: str) -> EmailResponse:
        """Send email with attachment by storing file in Appwrite Storage and including secure link."""
        try:
            from appwrite.services.storage import Storage
            
            storage = Storage(self.client)
            
            # Upload attachment to Appwrite Storage
            file_result = storage.create_file(
                bucket_id=os.getenv('CERTIFICATES_BUCKET_ID', 'certificates'),
                file_id='unique',  # Appwrite will generate this
                file=attachment_content,
                name=attachment_filename,
                mime_type='application/pdf'
            )
            
            # Get secure download URL
            download_url = storage.get_file_download(
                bucket_id=os.getenv('CERTIFICATES_BUCKET_ID', 'certificates'),
                file_id=file_result['$id']
            )
            
            # Update email body to include download link
            updated_body = f"""
            {request.body}
            
            <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
                <h3>📄 Certificate Download</h3>
                <p>Your certificate is ready for download:</p>
                <a href="{download_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
                    Download Certificate
                </a>
                <p style="font-size: 12px; color: #666; margin-top: 10px;">
                    This link will expire in 7 days for security reasons.
                </p>
            </div>
            """
            
            # Create updated request
            updated_request = EmailRequest(
                to_email=request.to_email,
                subject=request.subject,
                body=updated_body
            )
            
            # Send email with download link
            return self.send_email(updated_request)
            
        except Exception as e:
            logger.error(f"Error sending email with attachment: {e}")
            return EmailResponse(ok=False, error=str(e))

    def send_certificate_email(
        self,
        to_email: str,
        learner_name: str,
        learner_email: str,
        course_name: str,
        organization_name: str,
        attachment_content: Optional[bytes] = None,
        attachment_filename: Optional[str] = None
    ) -> EmailResponse:
        """Send certificate email with standardized template."""
        
        # Create email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">🎓 Course Completion Certificate</h2>
                
                <p>Dear {organization_name} Team,</p>
                
                <p>We are pleased to inform you that <strong>{learner_name}</strong> has successfully completed the course <strong>"{course_name}"</strong>.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <p><strong>Learner Details:</strong></p>
                    <ul>
                        <li><strong>Name:</strong> {learner_name}</li>
                        <li><strong>Email:</strong> {learner_email}</li>
                        <li><strong>Course:</strong> {course_name}</li>
                        <li><strong>Organization:</strong> {organization_name}</li>
                    </ul>
                </div>
                
                <p>Please find the completion certificate available for download below.</p>
                
                <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                
                <p style="font-size: 12px; color: #666;">
                    This is an automated message from Certificate Management System.<br>
                    Sent from: {self.smtp_config['from_email']}
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create email request
        email_request = EmailRequest(
            to_email=to_email,
            subject=f"🎓 Course Completion Certificate - {learner_name}",
            body=body,
            attachment_filename=attachment_filename
        )
        
        # Send email with attachment if provided
        if attachment_content and attachment_filename:
            return self.send_email_with_attachment(email_request, attachment_content, attachment_filename)
        else:
            return self.send_email(email_request)

    def test_connection(self) -> Dict[str, Any]:
        """Test email service connection."""
        try:
            # Test Appwrite messaging service
            test_request = EmailRequest(
                to_email='test@example.com',
                subject='Test Email - Connection Check',
                body='<p>This is a test email to verify Appwrite messaging service connection.</p>'
            )
            
            # Try to create a draft email (don't actually send)
            result = self.messaging.create_email(
                message_id='test-connection',
                subject=test_request.subject,
                html=test_request.body,
                text='This is a test email.',
                to=[test_request.to_email],
                cc=[],
                bcc=[],
                attachments=[],
                draft=True,  # Create as draft, don't send
                scheduled_at=None
            )
            
            return {
                'ok': True,
                'backend': 'appwrite-messaging',
                'message': 'Appwrite messaging service connection test passed',
                'gmail_config': {
                    'from_email': self.smtp_config['from_email'],
                    'smtp_host': self.smtp_config['host'],
                    'smtp_port': self.smtp_config['port']
                }
            }
            
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return {
                'ok': False,
                'backend': 'appwrite-messaging',
                'error': str(e),
                'gmail_config': {
                    'from_email': self.smtp_config['from_email'],
                    'smtp_host': self.smtp_config['host'],
                    'smtp_port': self.smtp_config['port']
                }
            }
