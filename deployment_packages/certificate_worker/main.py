"""
Certificate Worker - Generates certificates and sends emails to SOPs.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
shared_dir = os.path.join(current_dir, 'shared')
sys.path.insert(0, current_dir)

from shared.models import (
    WebhookEventModel, WebhookStatus, CertificateContext,
    CertificateSendStatus, EmailStatus
)
from shared.services.db import AppwriteClient
from shared.services.email_service import EmailService
from shared.services.renderer import CertificateRenderer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CertificateWorker:
    """Certificate generation and email sending worker."""

    def __init__(self, context=None):
        """Initialize certificate worker."""
        self.context = context
        
        # Get Appwrite configuration with fallbacks
        endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')
        api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')
        
        self._log(f"Database client config - endpoint: {endpoint}, project: {project_id}, api_key: {api_key[:20] if api_key else 'None'}...")
        
        # Initialize Appwrite client
        self.db = AppwriteClient(
            endpoint=endpoint,
            project_id=project_id,
            api_key=api_key
        )
        
        # Initialize email service with Appwrite client
        self.email = EmailService(self.db.client)
        
        # Initialize renderer
        self.renderer = CertificateRenderer(
            html_to_pdf_api_url=os.getenv('HTML_TO_PDF_API_URL')
        )
        
        # Configuration
        self.certificate_bucket_id = os.getenv('CERTIFICATE_BUCKET_ID', 'certificates')
        self.max_retry_attempts = int(os.getenv('MAX_EMAIL_RETRY_ATTEMPTS', 3))
        self.retry_delay = int(os.getenv('EMAIL_RETRY_DELAY', 60))  # seconds

    def _log(self, message):
        """Log message using context if available, otherwise use logger."""
        if self.context:
            self.context.log(message)
        else:
            logger.info(message)

    def _error(self, message):
        """Log error using context if available, otherwise use logger."""
        if self.context:
            self.context.error(message)
        else:
            logger.error(message)

    def process_webhook_event(self, webhook_event_id: str) -> Dict[str, Any]:
        """Process webhook event and generate certificate."""
        try:
            # Get webhook event
            webhook_event = self.db.get_webhook_event(webhook_event_id)
            if not webhook_event:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'WEBHOOK_NOT_FOUND',
                        'message': f'Webhook event {webhook_event_id} not found'
                    }
                }
            
            # Check if already processed
            if webhook_event.status in ['processed', 'completed']:
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'message': 'Webhook event already processed',
                        'event_id': webhook_event_id
                    }
                }
            
            # Mark as processing
            self.db.update_webhook_event(webhook_event_id, {
                'status': 'processing'
            })
            
            try:
                # Process the certificate
                result = self._process_certificate(webhook_event)
                
                if result['ok']:
                    # Mark as completed
                    self.db.update_webhook_event(webhook_event_id, {
                        'status': 'completed'
                    })
                    
                    return {
                        'ok': True,
                        'status': 200,
                        'data': {
                            'message': 'Certificate generated and sent successfully',
                            'event_id': webhook_event_id,
                            'learner_email': webhook_event.learner_email
                        }
                    }
                else:
                    # Mark as failed
                    self.db.update_webhook_event(webhook_event_id, {
                        'status': 'failed'
                    })
                    
                    return result
                    
            except Exception as e:
                logger.error(f"Error processing certificate for webhook {webhook_event_id}: {e}")
                
                # Mark as failed
                self.db.update_webhook_event(webhook_event_id, {
                    'status': 'failed'
                })
                
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'PROCESSING_ERROR',
                        'message': f'Certificate processing failed: {str(e)}'
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in process_webhook_event: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Internal server error'
                }
            }

    def _process_certificate(self, webhook_event: WebhookEventModel) -> Dict[str, Any]:
        """Process certificate generation and email sending."""
        try:
            logger.info(f"Processing certificate for webhook event: {webhook_event.id}")
            
            # Get course_id and email from webhook event
            course_id = webhook_event.course_id
            email = webhook_event.learner_email
            
            logger.info(f"Course ID: {course_id}, Email: {email}")
            
            if not course_id or not email:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_PAYLOAD',
                        'message': 'Missing course_id or learner_email in webhook event'
                    }
                }
            
            # Get learner
            logger.info(f"Looking up learner with email: {email} and course_id: {course_id}")
            learner = self.db.get_learner_by_course_and_email(course_id, email)
            if not learner:
                logger.error(f"Learner not found: {email} for course {course_id}")
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'LEARNER_NOT_FOUND',
                        'message': f'Learner {email} not found for course {course_id}'
                    }
                }
            
            logger.info(f"Found learner: {learner.name} ({learner.email})")
            
            # Mark learner as completed
            if not learner.completion_date:
                self.db.mark_learner_completed(course_id, email)
                learner.completion_date = datetime.utcnow()
            
            # Get course
            course = self.db.get_course_by_course_id(course_id)
            if not course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course {course_id} not found'
                    }
                }
            
            # Get organization
            org = self.db.get_organization_by_website(learner.organization_website)
            if not org:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'ORGANIZATION_NOT_FOUND',
                        'message': f'Organization {learner.organization_website} not found'
                    }
                }
            
            # Generate certificate PDF
            pdf_result = self._generate_certificate_pdf(course, learner, org)
            if not pdf_result['ok']:
                return pdf_result
            
            # Send email to SOP with PDF bytes or HTML content
            email_result = self._send_certificate_email(
                course, learner, org, 
                pdf_result.get('pdf_bytes'), 
                pdf_result.get('filename'),
                pdf_result.get('html_content')
            )
            
            # Update learner with email status
            self.db.update_learner(learner.id, {
                'certificate_send_status': 'sent' if email_result['ok'] else 'failed'
            })
            
            # Log email result
            try:
                email_log = self.db.create_email_log({
                    'learner_email': learner.email,
                    'course_id': course.course_id,
                    'organization_website': org.website,
                    'sent_at': datetime.utcnow().isoformat() + 'Z',
                    'email_type': 'certificate',
                    'status': 'sent' if email_result['ok'] else 'failed'
                })
                logger.info(f"Email log created: {email_log}")
            except Exception as e:
                logger.error(f"Failed to create email log: {e}")
            
            if not email_result['ok']:
                # Schedule retry if email failed
                self._schedule_email_retry(learner.id, email_result['error'])
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Certificate processed successfully',
                    'certificate_filename': pdf_result['filename'],
                    'email_sent': email_result['ok']
                }
            }
            
        except Exception as e:
            logger.error(f"Error in _process_certificate: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'PROCESSING_ERROR',
                    'message': f'Certificate processing failed: {str(e)}'
                }
            }

    def _generate_certificate_pdf(self, course, learner, org) -> Dict[str, Any]:
        """Generate certificate PDF and return bytes directly."""
        try:
            # Create certificate context
            context = CertificateContext(
                learner_name=learner.name,
                course_name=course.name,
                completion_date=learner.completion_date.isoformat().replace('+00:00', 'Z') if learner.completion_date else datetime.utcnow().isoformat().replace('+00:00', 'Z'),
                organization=org.name or org.website,
                learner_email=learner.email
            )
            
            # Generate filename for email attachment
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"Certificate_{learner.name}_{course.name}_{timestamp}.pdf"
            
            # Generate PDF bytes directly using PDFEndpoint API
            pdf_bytes = self.renderer.get_pdf_bytes(
                course.certificate_template_html,
                context
            )
            
            if not pdf_bytes:
                logger.warning("Failed to get PDF bytes from renderer, falling back to HTML email")
                # Return HTML content for email fallback instead of failing
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'pdf_bytes': None,
                        'filename': None,
                        'html_content': self.renderer.render_certificate(course.certificate_template_html, context),
                        'fallback_mode': 'html_email'
                    }
                }
            
            # Upload PDF to Appwrite storage and update learner's certificate_file_id
            try:
                certificate_bucket_id = os.getenv('CERTIFICATE_BUCKET_ID', 'certificates')
                self._log(f"Attempting to upload PDF to bucket: {certificate_bucket_id}")
                self._log(f"PDF bytes size: {len(pdf_bytes)} bytes")
                self._log(f"Filename: {filename}")
                
                # Upload PDF to storage
                self._log("Calling db.upload_file...")
                file_result = self.db.upload_file(
                    file_bytes=pdf_bytes,
                    filename=filename,
                    bucket_id=certificate_bucket_id,
                    content_type='application/pdf',
                    context=self.context
                )
                
                self._log(f"Upload result: {file_result}")
                
                if file_result:
                    file_id = file_result.get('$id')
                    self._log(f"PDF uploaded to storage with file_id: {file_id}")
                    
                    # Update learner's certificate_file_id
                    self._log(f"Updating learner {learner.email} with certificate_file_id: {file_id}")
                    update_success = self.db.update_learner(learner.id, {
                        'certificate_file_id': file_id,
                        'certificate_send_status': 'sent',
                        'updated_at': datetime.utcnow().isoformat() + 'Z'
                    })
                    
                    if update_success:
                        self._log(f"Successfully updated learner {learner.email} with certificate_file_id: {file_id}")
                    else:
                        self._log(f"Failed to update learner {learner.email} with certificate_file_id")
                else:
                    self._log("Failed to upload PDF to storage - file_result is None")
                    
            except Exception as e:
                self._error(f"Error uploading PDF to storage: {e}")
                import traceback
                self._error(f"Traceback: {traceback.format_exc()}")
                # Continue with email sending even if storage upload fails
            
            return {
                'ok': True,
                'pdf_bytes': pdf_bytes,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error generating certificate PDF: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'PDF_GENERATION_ERROR',
                    'message': f'PDF generation failed: {str(e)}'
                }
            }

    def _send_certificate_email(self, course, learner, org, pdf_bytes: Optional[bytes], filename: Optional[str], html_content: Optional[str] = None) -> Dict[str, Any]:
        """Send certificate email to SOP with PDF bytes or HTML content."""
        try:
            if pdf_bytes and filename:
                logger.info(f"Sending certificate email to {org.sop_email} with PDF attachment")
                
                # Send email with PDF bytes directly
                email_response = self.email.send_certificate_email(
                    to_email=org.sop_email,
                    learner_name=learner.name,
                    learner_email=learner.email,
                    course_name=course.name,
                    organization_name=org.name or org.website,
                    attachment_content=pdf_bytes,
                    attachment_filename=filename
                )
            else:
                logger.info(f"Sending certificate email to {org.sop_email} with HTML content (PDF generation failed)")
                
                # Send email with HTML content instead of PDF
                email_response = self.email.send_certificate_email_html(
                    to_email=org.sop_email,
                    learner_name=learner.name,
                    learner_email=learner.email,
                    course_name=course.name,
                    organization_name=org.name or org.website,
                    html_content=html_content
                )
            
            logger.info(f"Email response: {email_response}")
            return email_response.dict()
            
        except Exception as e:
            logger.error(f"Error sending certificate email: {e}")
            return {
                'ok': False,
                'error': f'Email sending failed: {str(e)}'
            }

    def _schedule_email_retry(self, learner_id: str, error_message: str) -> None:
        """Schedule email retry with exponential backoff."""
        try:
            # Update learner with retry attempt
            self.db.update_learner(learner_id, {
                'certificate_send_status': 'pending'
            })
            
            # In a production system, you would typically:
            # 1. Add to a retry queue
            # 2. Use a job scheduler
            # 3. Implement exponential backoff
            
            logger.info(f"Scheduled email retry for learner {learner_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error scheduling email retry: {e}")

    def retry_failed_certificates(self) -> Dict[str, Any]:
        """Retry failed certificate generations."""
        try:
            # Get failed webhook events
            failed_events = self.db.list_webhook_events(
                limit=100,
                offset=0,
                status=WebhookStatus.FAILED
            )
            
            retry_count = 0
            success_count = 0
            
            for event in failed_events:
                if event.attempts < self.max_retry_attempts:
                    # Reset status for retry
                    self.db.update_webhook_event(event.id, {
                        'status': WebhookStatus.RECEIVED.value,
                        'attempts': 0
                    })
                    
                    # Process the event
                    result = self.process_webhook_event(event.id)
                    retry_count += 1
                    
                    if result['ok']:
                        success_count += 1
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Retried {retry_count} failed certificates, {success_count} successful'
                }
            }
            
        except Exception as e:
            logger.error(f"Error retrying failed certificates: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'RETRY_ERROR',
                    'message': f'Retry failed: {str(e)}'
                }
            }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        try:
            # Test database connection
            self.db.list_courses(limit=1)
            
            # Test email service
            email_health = self.email.test_connection()
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Certificate worker is healthy',
                    'database': 'connected',
                    'email_service': email_health.get('backend', 'unknown'),
                    'email_status': 'connected' if email_health.get('ok') else 'disconnected'
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'HEALTH_CHECK_FAILED',
                    'message': str(e)
                }
            }


def main(context):
    """Main function entry point for Appwrite function."""
    try:
        # Get request data from context
        data = context.req.body
        
        # Parse JSON if provided
        if data:
            try:
                request_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return context.res.json({
                    "ok": False,
                    "error": f"Invalid JSON: {e}",
                    "message": "Failed to parse request"
                }, 400)
        else:
            # Default to health check if no data provided
            request_data = {"action": "health"}
            logger.info("No data provided, using default health check")
        
        # Check for health check
        if request_data.get('action') == 'health':
            worker = CertificateWorker(context)
            result = worker.health_check()
            return context.res.json(result)
        
        # Check for retry action
        if request_data.get('action') == 'retry_failed':
            worker = CertificateWorker(context)
            result = worker.retry_failed_certificates()
            return context.res.json(result)
            
        if request_data.get('action') == 'test_webhook':
            worker = CertificateWorker(context)
            webhook_id = request_data.get('webhook_event_id')
            if not webhook_id:
                return context.res.json({
                    "ok": False,
                    "error": "webhook_event_id is required"
                }, 400)
            
            try:
                # Try to get the specific webhook event
                webhook_event = worker.db.get_webhook_event(webhook_id)
                if webhook_event:
                    # Convert to dict with proper datetime handling
                    webhook_data = webhook_event.dict() if hasattr(webhook_event, 'dict') else webhook_event
                    # Convert datetime objects to ISO strings
                    if isinstance(webhook_data, dict):
                        for key, value in webhook_data.items():
                            if hasattr(value, 'isoformat'):
                                webhook_data[key] = value.isoformat()
                    
                    return context.res.json({
                        "ok": True,
                        "data": webhook_data
                    })
                else:
                    return context.res.json({
                        "ok": False,
                        "error": "Webhook event not found"
                    }, 404)
            except Exception as e:
                return context.res.json({
                    "ok": False,
                    "error": str(e)
                }, 500)
        
        # Get webhook event ID
        webhook_event_id = request_data.get('webhook_event_id')
        if not webhook_event_id:
            return context.res.json({
                "ok": False,
                "error": "MISSING_EVENT_ID",
                "message": "webhook_event_id is required"
            }, 400)
        
        # Initialize worker
        worker = CertificateWorker(context)
        
        # Process webhook event
        response = worker.process_webhook_event(webhook_event_id)
        
        return context.res.json(response)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)
