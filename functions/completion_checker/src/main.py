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
    CertificateSendStatus, EmailStatus, ActivityType, ActivityStatus
)
from shared.services.db import AppwriteClient
from shared.services.email_service_simple import EmailService
from shared.services.renderer import CertificateRenderer
from shared.services.graphy import GraphyService
from shared.services.activity_log import ActivityLogService
from appwrite.query import Query
import requests

logger = logging.getLogger(__name__)


class CompletionChecker:
    """Scheduled function to check course completions."""

    def __init__(self, context=None):
        """Initialize completion checker."""
        self.context = context
        
        # Get Appwrite configuration with fallbacks
        endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')
        api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')
        
        self._log(f"Database client config - endpoint: {endpoint}, project: {project_id}, api_key: {api_key[:20] if api_key else 'None'}...")
        
        self.db = AppwriteClient(
            endpoint=endpoint,
            project_id=project_id,
            api_key=api_key
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
        
        # Initialize activity log service
        self.activity_log = ActivityLogService(self.db.client)
        
        # Certificate worker configuration
        self.certificate_worker_url = f"{endpoint}/functions/certificate_worker/executions"
        self.certificate_worker_headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': project_id,
            'X-Appwrite-Key': api_key
        }

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

    def trigger_certificate_generation(self, webhook_event_id: str) -> Dict[str, Any]:
        """Trigger certificate generation by calling the certificate worker function."""
        try:
            self._log(f"Triggering certificate generation for webhook event: {webhook_event_id}")
            
            # Prepare the request payload
            payload = {
                "body": json.dumps({
                    "action": "process_webhook",
                    "webhook_event_id": webhook_event_id
                })
            }
            
            # Call the certificate worker function
            response = requests.post(
                self.certificate_worker_url,
                headers=self.certificate_worker_headers,
                json=payload,
                timeout=60  # 60 second timeout for certificate generation
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                self._log(f"Certificate worker response: {result}")
                return {
                    'ok': True,
                    'response': result
                }
            else:
                self._error(f"Certificate worker failed with status {response.status_code}: {response.text}")
                return {
                    'ok': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            self._error(f"Error triggering certificate generation: {e}")
            return {
                'ok': False,
                'error': str(e)
            }

    def get_enrolled_learners(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get learners with enrolled status."""
        try:
            self._log(f"Querying enrolled learners (limit: {limit}, offset: {offset})")
            
            # Use the Appwrite client directly to query learners
            result = self.db.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=[
                    Query.equal('enrollment_status', ['enrolled', 'pending']),
                    Query.not_equal('course_id', ''),
                    Query.limit(limit),
                    Query.offset(offset)
                ]
            )
            
            learners = result.get('documents', [])
            self._log(f"Found {len(learners)} enrolled learners")
            
            # Convert to dict format for compatibility
            learner_dicts = []
            for learner in learners:
                learner_dict = dict(learner)
                learner_dicts.append(learner_dict)
            
            return learner_dicts
                
        except Exception as e:
            self._error(f"Error getting enrolled learners: {e}")
            return []

    def check_completion_status(self, learner: Dict[str, Any]) -> Dict[str, Any]:
        """Check if learner has completed the course."""
        try:
            course_id = learner.get('course_id')
            email = learner.get('email')
            
            if not course_id or not email:
                return {'ok': False, 'error': 'Missing course_id or email'}
            
            # Get learner data from Graphy API
            result = self.graphy.get_learner_data(email)
            
            if result.get('ok'):
                learner_data = result.get('data', {})
                self._log(f"Graphy API response for {email}: {learner_data}")
                
                # Find the specific course
                courses = learner_data.get('courses', [])
                self._log(f"Found {len(courses)} courses for {email}")
                
                target_course = None
                for course in courses:
                    self._log(f"checking course id - Course {course.get('id')} against existing courseid: {course_id}")
                    if course.get('id') == course_id:
                        target_course = course
                        self._log(f"Found matching course: {target_course}")
                        break

                if not target_course:
                    self._log(f"Learner {email} - Course {course_id}: not found in learner data")
                    self._log(f"Available course IDs: {[course.get('id') for course in courses]}")
                    return {
                        'ok': True,
                        'completed': False,
                        'completion_percentage': 0,
                        'completion_data': {'error': 'Course not found in learner data'}
                    }

                # Check completion status
                progress = target_course.get('progress', 0)
                course_items = target_course.get('course items', [])
                
                self._log(f"Course progress: {progress}%, Course items: {len(course_items)}")

                # Determine if course is completed
                is_completed = False
                if progress >= 100:
                    # Check if all course items are completed
                    all_items_completed = True
                    for item in course_items:
                        if not item.get('completed', False):
                            all_items_completed = False
                            break
                    is_completed = all_items_completed
                    self._log(f"Progress >= 100%, all_items_completed: {all_items_completed}, is_completed: {is_completed}")
                else:
                    self._log(f"Progress < 100%, is_completed: {is_completed}")

                completion_data = {
                    'progress': progress,
                    'totalTime': target_course.get('totalTime', 0),
                    'course_items_count': len(course_items),
                    'completed_items': sum(1 for item in course_items if item.get('completed', False)),
                    'course_title': target_course.get('Title', ''),
                    'assigned_date': target_course.get('Assigned Date', ''),
                    'last_access_date': target_course.get('last access date', ''),
                    'start_date': target_course.get('start date', '')
                }

                self._log(f"Learner {email} - Course {course_id}: {progress}% progress, completed: {is_completed}")

                return {
                    'ok': True,
                    'completed': is_completed,
                    'completion_percentage': progress,
                    'completion_data': completion_data
                }
            else:
                self._error(f"Failed to get learner data for {email}: {result.get('error')}")
                return {'ok': False, 'error': result.get('error')}

                
        except Exception as e:
            self._error(f"Error checking completion status: {e}")
            return {'ok': False, 'error': str(e)}

    def update_learner_status(self, learner_id: str, status: str, completion_data: Dict[str, Any] = None, completion_percentage: float = 0.0) -> bool:
        """Update learner status in database."""
        try:
            self._log(f"Updating learner {learner_id} status to {status}")
            
            update_data = {
                'enrollment_status': status,
                'completion_percentage': completion_percentage,
                'last_completion_check': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if completion_data:
                update_data['completion_data'] = json.dumps(completion_data)
                # Only set completion_date if the course is actually completed
                if status == 'completed':
                    update_data['completion_date'] = datetime.utcnow().isoformat()
                    self._log(f"Setting completion_date for completed learner {learner_id}")
                self._log(f"Adding completion data for learner {learner_id}")
            
            # Use Appwrite client directly
            result = self.db.databases.update_document(
                database_id='main',
                collection_id='learners',
                document_id=learner_id,
                data=update_data
            )
            
            self._log(f"Successfully updated learner {learner_id} with status: {status}, completion_percentage: {completion_percentage}")
            return True
            
        except Exception as e:
            self._error(f"Error updating learner status for {learner_id}: {e}")
            return False

    def create_webhook_event(self, learner: Dict[str, Any], completion_data: Dict[str, Any]) -> str:
        """Create webhook event for certificate generation."""
        try:
            self._log(f"Creating webhook event for learner {learner.get('email')}")
            self._log(f"Learner data: {learner}")
            self._log(f"Completion data: {completion_data}")
            
            webhook_data = {
                'event_id': f"completion_{learner.get('email')}_{learner.get('course_id')}_{int(datetime.utcnow().timestamp())}",
                'learner_email': learner.get('email'),
                'course_id': learner.get('course_id'),
                'completion_date': datetime.utcnow().isoformat(),
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat()
            }
            
            self._log(f"Webhook data to create: {webhook_data}")
            
            # Use Appwrite client directly
            result = self.db.databases.create_document(
                database_id='main',
                collection_id='webhook_events',
                document_id='unique()',
                data=webhook_data
            )
            
            self._log(f"Appwrite create_document result: {result}")
            
            webhook_id = result.get('$id')
            self._log(f"Successfully created webhook event {webhook_id}")
            return webhook_id
                
        except Exception as e:
            self._error(f"Error creating webhook event: {e}")
            self._error(f"Exception details: {type(e).__name__}: {str(e)}")
            return None

    def process_batch(self, batch_size: int = 50) -> Dict[str, Any]:
        """Process a batch of learners for completion checking."""
        try:
            self._log(f"Starting completion check batch (size: {batch_size})")
            
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
                    
                    self._log(f"Checking completion for {email} in course {course_id}")
                    
                    # Check completion status
                    completion_result = self.check_completion_status(learner)
                    
                    if completion_result.get('ok'):
                        completion_percentage = completion_result.get('completion_percentage', 0)
                        
                        if completion_result.get('completed'):
                            # Learner has completed the course
                            self._log(f"Learner {email} has completed course {course_id}")
                            
                            # Log course completion activity
                            try:
                                # Get course and organization info for activity log
                                course = self.db.get_course_by_course_id(course_id)
                                course_name = course.name if course else f"Course {course_id}"
                                
                                self.activity_log.log_activity(
                                    activity_type=ActivityType.COMPLETION_CHECKED,
                                    actor="System",
                                    actor_email=None,
                                    actor_role="system",
                                    target=f"{learner.get('name', 'Unknown')} ({email})",
                                    organization_website=learner.get('organization_website'),
                                    details=f"Learner completed course: {course_name}",
                                    status=ActivityStatus.SUCCESS,
                                    metadata={
                                        'learner_email': email,
                                        'course_id': course_id,
                                        'course_name': course_name,
                                        'completion_percentage': completion_percentage,
                                        'completion_date': datetime.utcnow().isoformat() + 'Z'
                                    }
                                )
                                self._log(f"Logged course completion activity for {email}")
                            except Exception as log_error:
                                self._error(f"Failed to log course completion activity for {email}: {log_error}")
                            
                            # Update learner status with completion data
                            if self.update_learner_status(learner_id, 'completed', completion_result.get('completion_data'), completion_percentage):
                                # Create webhook event for certificate generation
                                webhook_event_id = self.create_webhook_event(learner, completion_result.get('completion_data'))
                                
                                if webhook_event_id:
                                    completed += 1
                                    self._log(f"Created webhook event {webhook_event_id} for {email}")
                                    
                                    # Immediately trigger certificate generation
                                    self._log(f"Triggering immediate certificate generation for {email}")
                                    cert_result = self.trigger_certificate_generation(webhook_event_id)
                                    
                                    if cert_result.get('ok'):
                                        self._log(f"Certificate generation triggered successfully for {email}")
                                    else:
                                        self._error(f"Certificate generation failed for {email}: {cert_result.get('error')}")
                                else:
                                    errors += 1
                                    self._error(f"Failed to create webhook event for {email}")
                            else:
                                errors += 1
                                self._error(f"Failed to update status for {email}")
                        else:
                            # Learner not completed yet - update progress
                            self._log(f"Learner {email} progress: {completion_percentage}%")
                            
                            # Update learner status with current progress
                            # Use 'enrolled' status for learners who are making progress but not completed
                            if not self.update_learner_status(learner_id, 'enrolled', completion_result.get('completion_data'), completion_percentage):
                                errors += 1
                                self._error(f"Failed to update progress for {email}")
                    else:
                        errors += 1
                        self._error(f"Failed to check completion for {email}: {completion_result.get('error')}")
                        
                except Exception as e:
                    errors += 1
                    self._error(f"Error processing learner {learner.get('email', 'unknown')}: {e}")
            
            return {
                'ok': True,
                'processed': processed,
                'completed': completed,
                'errors': errors,
                'message': f'Processed {processed} learners, {completed} completed, {errors} errors'
            }
            
        except Exception as e:
            self._error(f"Error in process_batch: {e}")
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
            self._log("Starting health check")
            
            # Test database connection
            db_status = "connected"
            try:
                result = self.db.databases.list_documents(
                    database_id='main',
                    collection_id='learners',
                    queries=[Query.limit(1)]
                )
                self._log("Database connection successful")
            except Exception as e:
                db_status = f"error: {str(e)}"
                self._error(f"Database connection failed: {e}")
            
            # Test Graphy API connection
            graphy_status = "disconnected"
            try:
                graphy_result = self.graphy.health_check()
                if graphy_result.get('ok'):
                    graphy_status = "connected"
                    self._log("Graphy API connection successful")
                else:
                    graphy_status = f"error: {graphy_result.get('error')}"
                    self._error(f"Graphy API connection failed: {graphy_result.get('error')}")
            except Exception as e:
                graphy_status = f"error: {str(e)}"
                self._error(f"Graphy API connection failed: {e}")
            
            health_result = {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Completion checker is healthy',
                    'database': db_status,
                    'graphy': graphy_status,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
            
            self._log(f"Health check completed: {health_result}")
            return health_result
            
        except Exception as e:
            self._error(f"Error in health check: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': str(e)
            }


def main(context):
    """Main function entry point for Appwrite function."""
    try:
        context.log("=== Completion Checker Function Started ===")
        
        # Get request data from context
        data = context.req.body
        context.log(f"Raw request data: {data}")
        
        # Parse JSON if provided
        if data:
            try:
                # Handle nested JSON structure like admin_router
                parsed_data = json.loads(data)
                context.log(f"Parsed request data: {parsed_data}")
                
                # Check if data is nested in 'body' field
                if 'body' in parsed_data:
                    request_data = json.loads(parsed_data['body'])
                    context.log(f"Extracted nested request data: {request_data}")
                else:
                    request_data = parsed_data
                    
            except json.JSONDecodeError as e:
                context.error(f"JSON decode error: {e}")
                return context.res.json({
                    "ok": False,
                    "error": f"Invalid JSON: {e}",
                    "message": "Failed to parse request"
                }, 400)
        else:
            # Default to health check if no data provided
            request_data = {"action": "health"}
            context.log("No data provided, using default health check")
        
        # Initialize checker
        context.log("Initializing CompletionChecker...")
        checker = CompletionChecker(context)
        context.log("CompletionChecker initialized successfully")
        
        # Handle different actions
        action = request_data.get('action', 'process_batch')
        context.log(f"Processing action: {action}")

        
        if action == 'health' or action == 'process_batch':
            batch_size = request_data.get('batch_size', 1000)
            context.log(f"Executing process_batch with batch_size: {batch_size}")
            result = checker.process_batch(batch_size)
            context.log(f"Process batch result: {result}")
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
                learner_result = checker.db.databases.get_document(
                    database_id='main',
                    collection_id='learners',
                    document_id=learner_id
                )
                
                learner_dict = dict(learner_result)
                completion_result = checker.check_completion_status(learner_dict)
                return context.res.json(completion_result)
                
            except Exception as e:
                context.error(f"Error getting learner {learner_id}: {e}")
                return context.res.json({
                    "ok": False,
                    "error": "LEARNER_NOT_FOUND",
                    "message": f"Learner {learner_id} not found: {str(e)}"
                }, 404)
        
        else:
            context.error(f"Unknown action: {action}")
            return context.res.json({
                "ok": False,
                "error": "INVALID_ACTION",
                "message": f"Unknown action: {action}"
            }, 400)
        
    except Exception as e:
        context.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)
