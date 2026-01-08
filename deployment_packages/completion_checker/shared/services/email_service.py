"""
Email service using Appwrite's built-in SMTP functionality.
"""

import logging
import os
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from appwrite.client import Client
    MESSAGING_AVAILABLE = True
    logger.info("Appwrite Client imported successfully")
except ImportError as e:
    MESSAGING_AVAILABLE = False
    logger.warning(f"Appwrite Client not available: {e}")
    class Client:
        pass

from ..models import EmailRequest, EmailResponse


class EmailService:
    """Email service using Appwrite's built-in SMTP functionality."""

    def __init__(self, appwrite_client: Client):
        """Initialize email service with Appwrite client."""
        self.client = appwrite_client
        logger.info(f"MESSAGING_AVAILABLE: {MESSAGING_AVAILABLE}")
        
        # Get Appwrite configuration
        self.endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        self.project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')
        self.api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')
        
        logger.info("Email service initialized with Appwrite HTTP API")
        
        # Gmail SMTP configuration (from environment variables)
        # If not set, fall back to defaults (for backward compatibility)
        gmail_username = os.getenv('GMAIL_USERNAME', 'decet2025@gmail.com')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD', 'yosamwzywwahzqbk')
        gmail_from = os.getenv('GMAIL_FROM_EMAIL', gmail_username)

        self.smtp_config = {
            'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'username': gmail_username,
            'password': gmail_password,
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            'from_email': gmail_from
        }

        logger.info(f"SMTP configured for: {self.smtp_config['username']} (host: {self.smtp_config['host']})")

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
            
            # Send email via direct SMTP (Appwrite messaging API only works with registered users)
            logger.info(f"Attempting to send email via direct SMTP to external address: {request.to_email}")
            
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.application import MIMEApplication
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = request.subject
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = request.to_email
            
            # Add text and HTML parts
            text_part = MIMEText(request.body.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n'), 'plain')
            html_part = MIMEText(request.body, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Add attachment if provided
            if attachment_content and request.attachment_filename:
                attachment = MIMEApplication(attachment_content, _subtype='pdf')
                attachment.add_header('Content-Disposition', 'attachment', filename=request.attachment_filename)
                msg.attach(attachment)
                logger.info(f"Added attachment: {request.attachment_filename}")
            
            # Send email via SMTP
            logger.info(f"Connecting to SMTP server: {self.smtp_config['host']}:{self.smtp_config['port']}")
            logger.info(f"Using credentials: {self.smtp_config['username']}")
            
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)
                logger.info(f"Email sent successfully to {request.to_email} via SMTP")
            
            result = {'$id': f'smtp-{int(time.time())}'}
            
            logger.info(f"Email sent successfully to {request.to_email} via Appwrite")
            return EmailResponse(
                ok=True,
                message_id=result.get('$id', 'appwrite-sent')
            )
                
        except Exception as e:
            logger.error(f"Error sending email via Appwrite: {e}")
            return EmailResponse(ok=False, error=str(e))

    def send_email_with_attachment(self, request: EmailRequest, attachment_content: bytes, attachment_filename: str) -> EmailResponse:
        """Send email with attachment via direct SMTP."""
        try:
            # Use the main send_email method which now handles attachments via SMTP
            return self.send_email(request, attachment_content)
                
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

    def send_certificate_email_html(
        self,
        to_email: str,
        learner_name: str,
        learner_email: str,
        course_name: str,
        organization_name: str,
        html_content: str
    ) -> EmailResponse:
        """Send certificate email with HTML content instead of PDF attachment."""
        try:
            # Create email request with HTML content
            email_request = EmailRequest(
                to_email=to_email,
                subject=f'Certificate of Completion - {course_name}',
                body=html_content  # HTML content is sent as the email body
            )
            
            logger.info(f"Sending HTML certificate email to {to_email}")
            return self.send_email(email_request)
            
        except Exception as e:
            logger.error(f"Error sending HTML certificate email: {e}")
            return EmailResponse(ok=False, error=str(e))

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
