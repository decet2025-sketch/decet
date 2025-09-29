"""
Completion Checker - Scheduled function to check course completions.
Runs periodically to check if enrolled learners have completed their courses.
"""

import json
import logging
import os
import sys
from typing import Dict, Any, List
from datetime import datetime, timedelta

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
from shared.services.graphy import GraphyService

logger = logging.getLogger(__name__)


class CompletionChecker:
    """Scheduled function to check course completions."""

    def __init__(self):
        """Initialize completion checker."""
        self.db = AppwriteClient(
            endpoint=os.getenv('APPWRITE_ENDPOINT'),
            project_id=os.getenv('APPWRITE_PROJECT'),
            api_key=os.getenv('APPWRITE_API_KEY')
        )
        
        # Initialize Graphy service
        self.graphy = GraphyService(
            api_base=os.getenv('GRAPHY_API_BASE', 'https://api.ongraphy.com'),
            api_key=os.getenv('GRAPHY_API_KEY'),
            merchant_id=os.getenv('GRAPHY_MERCHANT_ID')
        )
        
        # Initialize email service
        self.email = EmailService(self.db.client)
        
        # Initialize renderer
        self.renderer = CertificateRenderer()

    def get_enrolled_learners(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get learners with enrolled status."""
        try:
            # Query learners with enrolled status
            result = self.db.query_documents(
                collection_id='learners',
                filters=[
                    ('enrollment_status', '=', 'enrolled'),
                    ('course_id', '!=', '')
                ],
                limit=limit,
                offset=offset
            )
            
            if result.get('ok'):
                return result.get('data', [])
            else:
                logger.error(f"Error querying enrolled learners: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting enrolled learners: {e}")
            return []

    def check_completion_status(self, learner: Dict[str, Any]) -> Dict[str, Any]:
        """Check if learner has completed the course."""
        try:
            course_id = learner.get('course_id')
            email = learner.get('email')
            
            if not course_id or not email:
                return {'ok': False, 'error': 'Missing course_id or email'}
            
            # Check completion status via Graphy API
            result = self.graphy.get_completion_status(course_id, email)
            
            if result.get('ok'):
                data = result.get('data', {})
                is_completed = data.get('completed', False)
                completion_percentage = data.get('completion_percentage', 0)
                
                return {
                    'ok': True,
                    'completed': is_completed,
                    'completion_percentage': completion_percentage,
                    'completion_data': data
                }
            else:
                logger.warning(f"Failed to check completion for {email}: {result.get('error')}")
                return {'ok': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"Error checking completion status: {e}")
            return {'ok': False, 'error': str(e)}

    def update_learner_status(self, learner_id: str, status: str, completion_data: Dict[str, Any] = None) -> bool:
        """Update learner status in database."""
        try:
            update_data = {
                'enrollment_status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if completion_data:
                update_data['completion_data'] = json.dumps(completion_data)
                update_data['completion_date'] = datetime.utcnow().isoformat()
            
            result = self.db.update_document(
                collection_id='learners',
                document_id=learner_id,
                data=update_data
            )
            
            return result.get('ok', False)
            
        except Exception as e:
            logger.error(f"Error updating learner status: {e}")
            return False

    def create_webhook_event(self, learner: Dict[str, Any], completion_data: Dict[str, Any]) -> str:
        """Create webhook event for certificate generation."""
        try:
            webhook_data = {
                'event_type': 'course_completed',
                'learner_email': learner.get('email'),
                'course_id': learner.get('course_id'),
                'organization_id': learner.get('organization_id'),
                'completion_data': completion_data,
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'source': 'scheduler'
            }
            
            result = self.db.create_document(
                collection_id='webhook_events',
                data=webhook_data
            )
            
            if result.get('ok'):
                return result.get('data', {}).get('$id')
            else:
                logger.error(f"Error creating webhook event: {result.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating webhook event: {e}")
            return None

    def process_batch(self, batch_size: int = 50) -> Dict[str, Any]:
        """Process a batch of learners for completion checking."""
        try:
            logger.info(f"Starting completion check batch (size: {batch_size})")
            
            # Get enrolled learners
            learners = self.get_enrolled_learners(limit=batch_size)
            
            if not learners:
                return {
                    'ok': True,
                    'processed': 0,
                    'completed': 0,
                    'errors': 0,
                    'message': 'No enrolled learners found'
                }
            
            processed = 0
            completed = 0
            errors = 0
            
            for learner in learners:
                try:
                    processed += 1
                    learner_id = learner.get('$id')
                    email = learner.get('email')
                    course_id = learner.get('course_id')
                    
                    logger.info(f"Checking completion for {email} in course {course_id}")
                    
                    # Check completion status
                    completion_result = self.check_completion_status(learner)
                    
                    if completion_result.get('ok'):
                        if completion_result.get('completed'):
                            # Learner has completed the course
                            logger.info(f"Learner {email} has completed course {course_id}")
                            
                            # Update learner status
                            if self.update_learner_status(learner_id, 'completed', completion_result.get('completion_data')):
                                # Create webhook event for certificate generation
                                webhook_event_id = self.create_webhook_event(learner, completion_result.get('completion_data'))
                                
                                if webhook_event_id:
                                    completed += 1
                                    logger.info(f"Created webhook event {webhook_event_id} for {email}")
                                else:
                                    errors += 1
                                    logger.error(f"Failed to create webhook event for {email}")
                            else:
                                errors += 1
                                logger.error(f"Failed to update status for {email}")
                        else:
                            # Learner not completed yet
                            completion_percentage = completion_result.get('completion_percentage', 0)
                            logger.info(f"Learner {email} progress: {completion_percentage}%")
                    else:
                        errors += 1
                        logger.warning(f"Failed to check completion for {email}: {completion_result.get('error')}")
                        
                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing learner {learner.get('email', 'unknown')}: {e}")
            
            return {
                'ok': True,
                'processed': processed,
                'completed': completed,
                'errors': errors,
                'message': f'Processed {processed} learners, {completed} completed, {errors} errors'
            }
            
        except Exception as e:
            logger.error(f"Error in process_batch: {e}")
            return {
                'ok': False,
                'error': str(e),
                'processed': 0,
                'completed': 0,
                'errors': 0
            }

    def health_check(self) -> Dict[str, Any]:
        """Health check for the completion checker."""
        try:
            # Test database connection
            db_status = "connected"
            try:
                self.db.list_documents('learners', limit=1)
            except Exception as e:
                db_status = f"error: {str(e)}"
            
            # Test Graphy API connection
            graphy_status = "disconnected"
            try:
                graphy_result = self.graphy.health_check()
                if graphy_result.get('ok'):
                    graphy_status = "connected"
                else:
                    graphy_status = f"error: {graphy_result.get('error')}"
            except Exception as e:
                graphy_status = f"error: {str(e)}"
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Completion checker is healthy',
                    'database': db_status,
                    'graphy': graphy_status,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': str(e)
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
        
        # Initialize checker
        checker = CompletionChecker()
        
        # Handle different actions
        action = request_data.get('action', 'process_batch')
        
        if action == 'health':
            result = checker.health_check()
            return context.res.json(result)
        
        elif action == 'process_batch':
            batch_size = request_data.get('batch_size', 50)
            result = checker.process_batch(batch_size)
            return context.res.json(result)
        
        elif action == 'check_specific':
            learner_id = request_data.get('learner_id')
            if not learner_id:
                return context.res.json({
                    "ok": False,
                    "error": "MISSING_LEARNER_ID",
                    "message": "learner_id is required for check_specific action"
                }, 400)
            
            # Get specific learner and check completion
            try:
                learner = checker.db.get_document('learners', learner_id)
                if learner.get('ok'):
                    completion_result = checker.check_completion_status(learner.get('data'))
                    return context.res.json(completion_result)
                else:
                    return context.res.json({
                        "ok": False,
                        "error": "LEARNER_NOT_FOUND",
                        "message": f"Learner {learner_id} not found"
                    }, 404)
            except Exception as e:
                return context.res.json({
                    "ok": False,
                    "error": str(e),
                    "message": "Error checking specific learner"
                }, 500)
        
        else:
            return context.res.json({
                "ok": False,
                "error": "INVALID_ACTION",
                "message": f"Unknown action: {action}"
            }, 400)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)
