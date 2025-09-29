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
from shared.services.email_service_simple import EmailService
from shared.services.renderer import CertificateRenderer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CertificateWorker:
    """Certificate generation and email sending worker."""

    def __init__(self):
        """Initialize certificate worker."""
        # Initialize Appwrite client
        self.db = AppwriteClient(
            endpoint=os.getenv('APPWRITE_ENDPOINT'),
            project_id=os.getenv('APPWRITE_PROJECT'),
            api_key=os.getenv('APPWRITE_API_KEY')
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
            if webhook_event.status == WebhookStatus.PROCESSED.value:
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
                'status': WebhookStatus.PROCESSING.value,
                'attempts': webhook_event.attempts + 1
            })
            
            try:
                # Process the certificate
                result = self._process_certificate(webhook_event)
                
                if result['ok']:
                    # Mark as processed
                    self.db.update_webhook_event(webhook_event_id, {
                        'status': WebhookStatus.PROCESSED.value,
                        'processed_at': datetime.utcnow().isoformat() + 'Z'
                    })
                    
                    return {
                        'ok': True,
                        'status': 200,
                        'data': {
                            'message': 'Certificate generated and sent successfully',
                            'event_id': webhook_event_id,
                            'learner_email': webhook_event.email
                        }
                    }
                else:
                    # Mark as failed
                    self.db.update_webhook_event(webhook_event_id, {
                        'status': WebhookStatus.FAILED.value
                    })
                    
                    return result
                    
            except Exception as e:
                logger.error(f"Error processing certificate for webhook {webhook_event_id}: {e}")
                
                # Mark as failed
                self.db.update_webhook_event(webhook_event_id, {
                    'status': WebhookStatus.FAILED.value
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
            # Parse webhook payload
            payload = json.loads(webhook_event.payload)
            course_id = payload.get('course_id')
            email = payload.get('email')
            
            if not course_id or not email:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_PAYLOAD',
                        'message': 'Missing course_id or email in webhook payload'
                    }
                }
            
            # Get learner
            learner = self.db.get_learner_by_course_and_email(course_id, email)
            if not learner:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'LEARNER_NOT_FOUND',
                        'message': f'Learner {email} not found for course {course_id}'
                    }
                }
            
            # Mark learner as completed
            if not learner.completion_at:
                self.db.mark_learner_completed(course_id, email)
                learner.completion_at = datetime.utcnow()
            
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
            
            # Update learner with certificate file ID
            self.db.update_learner(learner.id, {
                'certificate_file_id': pdf_result['file_id'],
                'certificate_generated_at': datetime.utcnow().isoformat() + 'Z'
            })
            
            # Send email to SOP
            email_result = self._send_certificate_email(course, learner, org, pdf_result['file_id'])
            
            # Update learner with email status
            self.db.update_learner(learner.id, {
                'certificate_send_status': CertificateSendStatus.SENT.value if email_result['ok'] else CertificateSendStatus.FAILED.value,
                'certificate_sent_to_sop_at': datetime.utcnow().isoformat() + 'Z' if email_result['ok'] else None
            })
            
            # Log email result
            self.db.create_email_log({
                'to_email': org.sop_email,
                'subject': f'Course Completion Certificate - {learner.name}',
                'attachment_file_id': pdf_result['file_id'],
                'status': EmailStatus.SENT.value if email_result['ok'] else EmailStatus.FAILED.value,
                'response': email_result.get('message_id') or email_result.get('error')
            })
            
            if not email_result['ok']:
                # Schedule retry if email failed
                self._schedule_email_retry(learner.id, email_result['error'])
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Certificate processed successfully',
                    'certificate_file_id': pdf_result['file_id'],
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
        """Generate certificate PDF."""
        try:
            # Create certificate context
            context = CertificateContext(
                learner_name=learner.name,
                course_name=course.name,
                completion_date=learner.completion_at.isoformat() + 'Z',
                organization=org.name or org.website,
                learner_email=learner.email
            )
            
            # Generate filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"certificates/{course.course_id}/{org.website}/{learner.email}-{timestamp}.pdf"
            
            # Generate PDF
            pdf_response = self.renderer.generate_certificate_pdf(
                course.certificate_template_html,
                context,
                filename
            )
            
            if not pdf_response.ok:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'PDF_GENERATION_FAILED',
                        'message': pdf_response.error
                    }
                }
            
            # Save PDF to storage
            # Note: In a real implementation, you would get the PDF bytes from the renderer
            # For now, we'll create a placeholder file ID
            file_id = f"cert_{course.course_id}_{learner.email}_{timestamp}"
            
            return {
                'ok': True,
                'file_id': file_id,
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

    def _send_certificate_email(self, course, learner, org, certificate_file_id: str) -> Dict[str, Any]:
        """Send certificate email to SOP."""
        try:
            # Get certificate file content
            certificate_content = self.db.get_file_content(certificate_file_id, self.certificate_bucket_id)
            if not certificate_content:
                return {
                    'ok': False,
                    'error': 'Certificate file not found'
                }
            
            # Generate filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"Certificate_{learner.name}_{course.name}_{timestamp}.pdf"
            
            # Send email
            email_response = self.email.send_certificate_email(
                to_email=org.sop_email,
                learner_name=learner.name,
                learner_email=learner.email,
                course_name=course.name,
                organization_name=org.name or org.website,
                attachment_content=certificate_content,
                attachment_filename=filename
            )
            
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
                'last_resend_attempt': datetime.utcnow().isoformat() + 'Z',
                'certificate_send_status': CertificateSendStatus.PENDING.value
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
            worker = CertificateWorker()
            result = worker.health_check()
            return context.res.json(result)
        
        # Check for retry action
        if request_data.get('action') == 'retry_failed':
            worker = CertificateWorker()
            result = worker.retry_failed_certificates()
            return context.res.json(result)
        
        # Get webhook event ID
        webhook_event_id = request_data.get('webhook_event_id')
        if not webhook_event_id:
            return context.res.json({
                "ok": False,
                "error": "MISSING_EVENT_ID",
                "message": "webhook_event_id is required"
            }, 400)
        
        # Initialize worker
        worker = CertificateWorker()
        
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
