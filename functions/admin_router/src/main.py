"""
Admin Router - Main entrypoint for all admin operations.
"""

import csv
import io
import json
import logging
import os
import re
import sys
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
shared_dir = os.path.join(current_dir, 'shared')
sys.path.insert(0, current_dir)

from shared.models import (
    ActionRequest, ActionType, BaseResponse,
    CreateCoursePayload, EditCoursePayload, DeleteCoursePayload,
    PreviewCertificatePayload, ListCoursesPayload, ViewLearnersPayload, ListAllLearnersPayload,
    AddOrganizationPayload, EditOrganizationPayload, DeleteOrganizationPayload, ListOrganizationsPayload, ResetSOPPasswordPayload,
    UploadLearnersCSVPayload, UploadLearnersCSVDirectPayload, ResendCertificatePayload, DownloadCertificatePayload, ListWebhooksPayload,
    RetryWebhookPayload, CSVValidationResult, UploadResult, EnrollmentResult,
    CertificateContext, LearnerCSVRow, GraphyEnrollmentRequest,
    ListActivityLogsPayload, ActivityType, ActivityStatus,
    LearnerStatisticsPayload, OrganizationStatisticsPayload, CourseStatisticsPayload,
    LearnerModel
)
from shared.services.db import AppwriteClient
from shared.services.graphy import GraphyService
from shared.services.email_service_simple import EmailService
from shared.services.renderer import CertificateRenderer
from shared.services.auth import AuthService
from shared.services.activity_log import ActivityLogService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdminRouter:
    """Main admin router class."""

    def __init__(self):
        """Initialize admin router with services."""
        # Initialize Appwrite client
        endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')  # Fallback to project ID
        api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')
        
        logger.info(f"Database client config - endpoint: {endpoint}, project: {project_id}, api_key: {api_key[:20] if api_key else 'None'}...")
        
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
        self.renderer = CertificateRenderer(
            html_to_pdf_api_url=os.getenv('HTML_TO_PDF_API_URL')
        )
        
        # Initialize auth service
        self.auth = AuthService()
        
        # Initialize activity log service
        self.activity_log = ActivityLogService(
            client=self.db.client,
            database_id='main'
        )

        self.certificate_worker_url = f"{endpoint}/functions/certificate_worker/executions"
        self.certificate_worker_headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': project_id,
            'X-Appwrite-Key': api_key
        }

    def _parse_course_id_from_url(self, course_url: str) -> Optional[str]:
        """
        Parse course ID from Graphy course URL.
        
        URL format: https://sharondecet.graphy.com/courses/201-Georgia-Basic-Security-Officer-Course--24-hours-67fbd49f6fdfb6161c8dde74
        Course ID: 67fbd49f6fdfb6161c8dde74 (last part after the last dash)
        """
        if not course_url:
            return None
            
        try:
            # Extract the last part of the URL path
            # Split by '/' and get the last segment
            url_parts = course_url.split('/')
            if len(url_parts) < 2:
                return None
                
            course_slug = url_parts[-1]
            
            # The course ID is the last part after the final dash
            # Split by '-' and get the last segment
            slug_parts = course_slug.split('-')
            if len(slug_parts) < 2:
                return None
                
            course_id = slug_parts[-1]
            
            # Validate that it looks like a course ID (alphanumeric, reasonable length)
            # Updated to accept course IDs with 16+ characters (was 20+)
            if re.match(r'^[a-f0-9]{16,}$', course_id):
                return course_id
            else:
                logger.warning(f"Extracted course ID '{course_id}' doesn't match expected format (should be 16+ hex characters)")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing course ID from URL '{course_url}': {e}")
            return None

    def _handle_user_creation(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user creation endpoints (CREATE_ADMIN_USER, CREATE_SOP_USER)."""
        try:
            action = request_data.get('action')
            payload = request_data.get('payload', {})
            
            if action == 'CREATE_ADMIN_USER':
                return self._create_admin_user(payload)
            elif action == 'CREATE_SOP_USER':
                return self._create_sop_user(payload)
            else:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_ACTION',
                        'message': f'Invalid action: {action}'
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in user creation: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': str(e)
                }
            }

    def _create_admin_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an admin user and return JWT token."""
        try:
            email = payload.get('email')
            name = payload.get('name')
            password = payload.get('password')
            
            if not all([email, name, password]):
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'MISSING_FIELDS',
                        'message': 'email, name, and password are required'
                    }
                }
            
            # Create user in Appwrite Users collection
            user_result = self.auth.create_user_in_appwrite(
                email=email,
                password=password,
                name=name,
                role='admin'
            )
            
            if not user_result['ok']:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'USER_CREATION_FAILED',
                        'message': user_result.get('error', 'Failed to create user')
                    }
                }
            
            user_data = user_result['data']
            user_id = user_data['$id']
            is_existing = user_data.get('existing', False)
            
            # If user already exists, validate the password and role
            if is_existing:
                # Get the user's actual role from Appwrite
                actual_role = self.auth.get_user_role(user_id)
                if actual_role != 'admin':
                    return {
                        'ok': False,
                        'status': 403,
                        'error': {
                            'code': 'INVALID_ROLE',
                            'message': f'User {email} is not an admin user. Cannot login with admin credentials.'
                        }
                    }
                
                # Validate password for existing user
                password_valid = self.auth.validate_user_password(email, password)
                if not password_valid:
                    return {
                        'ok': False,
                        'status': 401,
                        'error': {
                            'code': 'INVALID_PASSWORD',
                            'message': 'Invalid password!'
                        }
                    }
            
            # Generate JWT token
            token = self.auth.create_jwt_token({
                'user_id': user_id,
                'email': email,
                'role': 'admin',
                'name': name
            })
            
            message = 'Admin user created successfully' if not is_existing else 'Admin user login successful'
            
            return {
                'ok': True,
                'status': 201 if not is_existing else 200,
                'data': {
                    'user_id': user_id,
                    'email': email,
                    'name': name,
                    'role': 'admin',
                    'token': token,
                    'message': message,
                    'existing': is_existing
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating admin user: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'CREATION_FAILED',
                    'message': str(e)
                }
            }

    def _create_sop_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SOP user login - authenticate and return JWT token."""
        try:
            email = payload.get('email')
            password = payload.get('password')

            if not all([email, password]):
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'MISSING_FIELDS',
                        'message': 'email and password are required'
                    }
                }

            # Authenticate user using existing auth service
            try:
                # Get user by email to verify they exist and get their details
                from appwrite.services.users import Users
                from appwrite.id import ID
                
                # Get user by email to verify they exist and get their details
                users = Users(self.db.client)
                user_list = users.list()
                
                # Find exact email match
                user = None
                if user_list['total'] > 0:
                    for u in user_list['users']:
                        if u.get('email', '').lower() == email.lower():
                            user = u
                            break
                
                if not user:
                    return {
                        'ok': False,
                        'status': 401,
                        'error': {
                            'code': 'AUTH_FAILED',
                            'message': 'Invalid email or password'
                        }
                    }
                
                # Check if user has SOP role
                actual_role = self.auth.get_user_role(user['$id'])
                if actual_role != 'sop':
                    return {
                        'ok': False,
                        'status': 403,
                        'error': {
                            'code': 'INVALID_ROLE',
                            'message': f'User {email} is not a SOP user. Cannot login with SOP credentials.'
                        }
                    }
                
                # Get organization from user preferences
                user_prefs = user.get('prefs', {})
                organization_website = user_prefs.get('organization_website')
                
                if not organization_website:
                    return {
                        'ok': False,
                        'status': 400,
                        'error': {
                            'code': 'NO_ORGANIZATION',
                            'message': 'User does not have an organization assigned'
                        }
                    }
                
                # Get organization details
                organization = self.db.get_organization_by_website(organization_website)
                if not organization:
                    return {
                        'ok': False,
                        'status': 404,
                        'error': {
                            'code': 'ORGANIZATION_NOT_FOUND',
                            'message': f'Organization with website {organization_website} not found'
                        }
                    }
                
                # Validate that the user's email matches the organization's sop_email
                if organization.sop_email != email:
                    return {
                        'ok': False,
                        'status': 403,
                        'error': {
                            'code': 'UNAUTHORIZED_SOP',
                            'message': 'Not authorized to access this organization'
                        }
                    }
                
                # Validate password for SOP user
                password_valid = self.auth.validate_user_password(email, password)
                if not password_valid:
                    return {
                        'ok': False,
                        'status': 401,
                        'error': {
                            'code': 'INVALID_PASSWORD',
                            'message': 'Invalid password for SOP user'
                        }
                    }
                
                # Generate JWT token
                token = self.auth.create_jwt_token({
                    'user_id': user['$id'],
                    'email': user['email'],
                    'role': 'sop',
                    'name': user['name'],
                    'organization_website': organization_website
                })
                
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'user_id': user['$id'],
                        'email': user['email'],
                        'name': user['name'],
                        'role': 'sop',
                        'token': token,
                        'message': 'SOP user login successful',
                        'organization': {
                            'id': organization.id,
                            'website': organization.website,
                            'name': organization.name,
                            'sop_email': organization.sop_email,
                            'created_at': organization.created_at.isoformat() if organization.created_at else None,
                            'updated_at': organization.updated_at.isoformat() if organization.updated_at else None
                        }
                    }
                }
                    
            except Exception as auth_error:
                logger.error(f"Authentication error: {auth_error}")
                return {
                    'ok': False,
                    'status': 401,
                    'error': {
                        'code': 'AUTH_FAILED',
                        'message': 'Invalid email or password'
                    }
                }

        except Exception as e:
            logger.error(f"Error creating sop user: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'CREATION_FAILED',
                    'message': str(e)
                }
            }

    def handle_request(self, context, request_data: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Handle incoming admin request."""
        try:
            # Handle headers
            if headers is None:
                headers = {}
            
            # Check for unauthenticated endpoints first
            action = request_data.get('action')
            context.log(f"get into router 2 : {str(action)}")
            if action in ['CREATE_ADMIN_USER', 'CREATE_SOP_USER']:
                return self._handle_user_creation(request_data)
            
            # Validate authentication for all other endpoints
            auth_context = self.auth.validate_request_auth(headers)
            if not auth_context or not self.auth.require_admin(auth_context):
                return self.auth.create_unauthorized_response()
            
            # Parse request
            try:
                action_request = ActionRequest(**request_data)
            except Exception as e:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': f'Invalid request format: {str(e)}'
                    }
                }
            
            # Route to appropriate handler
            handler_map = {
                ActionType.CREATE_COURSE: self._handle_create_course,
                ActionType.EDIT_COURSE: self._handle_edit_course,
                ActionType.DELETE_COURSE: self._handle_delete_course,
                ActionType.UPLOAD_LEARNERS_CSV: self._handle_upload_learners_csv,
                ActionType.UPLOAD_LEARNERS_CSV_DIRECT: self._handle_upload_learners_csv_direct,
                ActionType.PREVIEW_CERTIFICATE: self._handle_preview_certificate,
                ActionType.LIST_COURSES: self._handle_list_courses,
                ActionType.VIEW_LEARNERS: self._handle_view_learners,
                ActionType.LIST_ALL_LEARNERS: self._handle_list_all_learners,
                ActionType.ADD_ORGANIZATION: self._handle_add_organization,
                ActionType.EDIT_ORGANIZATION: self._handle_edit_organization,
                ActionType.DELETE_ORGANIZATION: self._handle_delete_organization,
                ActionType.LIST_ORGANIZATIONS: self._handle_list_organizations,
                ActionType.RESET_SOP_PASSWORD: self._handle_reset_sop_password,
                ActionType.RESEND_CERTIFICATE: self._handle_resend_certificate,
                ActionType.DOWNLOAD_CERTIFICATE: self._handle_download_certificate,
                ActionType.LIST_WEBHOOKS: self._handle_list_webhooks,
                ActionType.RETRY_WEBHOOK: self._handle_retry_webhook,
                ActionType.LIST_ACTIVITY_LOGS: self._handle_list_activity_logs,
                ActionType.LEARNER_STATISTICS: self._handle_learner_statistics,
                ActionType.ORGANIZATION_STATISTICS: self._handle_organization_statistics,
                ActionType.COURSE_STATISTICS: self._handle_course_statistics,
            }
            
            handler = handler_map.get(action_request.action)
            context.log(f"handler : {handler.__name__}")
            if not handler:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_ACTION',
                        'message': f'Unknown action: {action_request.action}'
                    }
                }
            
            # Execute handler
            return handler(action_request.payload, auth_context)
            
        except Exception as e:
            import traceback
            logger.error(f"Error handling admin request: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Internal server error'
                }
            }

    def _handle_create_course(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle CREATE_COURSE action."""
        try:
            # Validate payload
            course_data = CreateCoursePayload(**payload)
            
            # Parse course ID from URL if course_url is provided and course_id is not
            final_course_id = course_data.course_id
            if course_data.course_url and not course_data.course_id:
                parsed_course_id = self._parse_course_id_from_url(course_data.course_url)
                if parsed_course_id:
                    final_course_id = parsed_course_id
                    logger.info(f"Parsed course ID '{parsed_course_id}' from URL: {course_data.course_url}")
                else:
                    return {
                        'ok': False,
                        'status': 400,
                        'error': {
                            'code': 'INVALID_COURSE_URL',
                            'message': 'Could not parse course ID from the provided URL'
                        }
                    }
            
            # Check if course already exists
            existing_course = self.db.get_course_by_course_id(final_course_id)
            if existing_course:
                return {
                    'ok': False,
                    'status': 409,
                    'error': {
                        'code': 'COURSE_EXISTS',
                        'message': f'Course with ID {final_course_id} already exists'
                    }
                }
            
            # Create course
            course = self.db.create_course({
                'course_id': final_course_id,
                'name': course_data.name,
                'certificate_template_html': course_data.certificate_template_html,
                'course_url': course_data.course_url
            })
            
            if not course:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'CREATE_FAILED',
                        'message': 'Failed to create course'
                    }
                }
            
            # Log activity (with error handling to not break main functionality)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.COURSE_CREATED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=course_data.name,
                    course_id=final_course_id,
                    details=f"Course {course_data.name} created and activated",
                    status=ActivityStatus.SUCCESS
                )
            except Exception as log_error:
                logger.warning(f"Failed to log course creation activity: {log_error}")
            
            return {
                'ok': True,
                'status': 201,
                'data': {
                    'course': json.loads(course.json())
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating course: {e}")
            
            # Log failed activity (with error handling)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.COURSE_CREATED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=payload.get('name', 'Unknown Course'),
                    course_id=payload.get('course_id') or payload.get('course_url', 'unknown'),
                    details=f"Course creation failed: {str(e)}",
                    status=ActivityStatus.FAILED,
                    error_message=str(e)
                )
            except Exception as log_error:
                logger.warning(f"Failed to log course creation failure activity: {log_error}")
            
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_edit_course(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle EDIT_COURSE action."""
        try:
            # Validate payload
            course_data = EditCoursePayload(**payload)
            
            # Check if course exists
            existing_course = self.db.get_course_by_course_id(course_data.course_id)
            if not existing_course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {course_data.course_id} not found'
                    }
                }
            
            # Prepare update data
            update_data = {}
            if course_data.name is not None:
                update_data['name'] = course_data.name
            if course_data.certificate_template_html is not None:
                update_data['certificate_template_html'] = course_data.certificate_template_html
            
            # Update course
            updated_course = self.db.update_course(course_data.course_id, update_data)
            
            if not updated_course:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'UPDATE_FAILED',
                        'message': 'Failed to update course'
                    }
                }
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'course': json.loads(updated_course.json())
                }
            }
            
        except Exception as e:
            logger.error(f"Error editing course: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_delete_course(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle DELETE_COURSE action."""
        try:
            # Validate payload
            course_data = DeleteCoursePayload(**payload)
            
            # Check if course exists
            existing_course = self.db.get_course_by_course_id(course_data.course_id)
            if not existing_course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {course_data.course_id} not found'
                    }
                }
            
            # Delete course
            success = self.db.delete_course(course_data.course_id)
            
            if not success:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'DELETE_FAILED',
                        'message': 'Failed to delete course'
                    }
                }
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Course {course_data.course_id} deleted successfully'
                }
            }
            
        except Exception as e:
            logger.error(f"Error deleting course: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_upload_learners_csv(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle UPLOAD_LEARNERS_CSV action."""
        try:
            # Validate payload
            upload_data = UploadLearnersCSVPayload(**payload)
            
            # Check if course exists
            course = self.db.get_course_by_course_id(upload_data.course_id)
            if not course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {upload_data.course_id} not found'
                    }
                }
            
            # Download CSV from storage
            csv_content = self.db.get_file_content(upload_data.csv_file_id, 'csv-uploads')
            if not csv_content:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'FILE_NOT_FOUND',
                        'message': 'CSV file not found in storage'
                    }
                }
            
            # Parse and validate CSV
            validation_result = self._parse_and_validate_csv(csv_content, upload_data.course_id)
            
            # Process valid rows
            upload_result = self._process_learner_enrollments(validation_result, upload_data.course_id)
            
            # Log activity (with error handling to not break main functionality)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.BULK_UPLOAD,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=course.name,
                    course_id=upload_data.course_id,
                    details=f"{upload_result.created_learners} learners uploaded to {course.name} via CSV file",
                    status=ActivityStatus.SUCCESS,
                    metadata={
                        'total_rows': upload_result.total_rows,
                        'valid_rows': upload_result.valid_rows,
                        'invalid_rows': upload_result.invalid_rows,
                        'duplicate_rows': upload_result.duplicate_rows,
                        'created_learners': upload_result.created_learners,
                        'enrollment_success': upload_result.enrollment_success,
                        'enrollment_failed': upload_result.enrollment_failed,
                        'csv_file_id': upload_data.csv_file_id
                    }
                )
            except Exception as log_error:
                logger.warning(f"Failed to log bulk upload activity: {log_error}")
            
            return {
                'ok': True,
                'status': 200,
                'data': upload_result.dict()
            }
            
        except Exception as e:
            logger.error(f"Error uploading learners CSV: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_upload_learners_csv_direct(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle UPLOAD_LEARNERS_CSV_DIRECT action."""
        try:
            # Validate payload
            upload_data = UploadLearnersCSVDirectPayload(**payload)
            
            # Check if course exists
            course = self.db.get_course_by_course_id(upload_data.course_id)
            if not course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {upload_data.course_id} not found'
                    }
                }
            
            # Parse and validate CSV
            validation_result = self._parse_and_validate_csv_direct(upload_data.csv_data, upload_data.course_id)
            
            # Process valid rows
            upload_result = self._process_learner_enrollments(validation_result, upload_data.course_id)
            
            # Log activity (with error handling to not break main functionality)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.BULK_UPLOAD,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=course.name,
                    course_id=upload_data.course_id,
                    details=f"{upload_result.created_learners} learners uploaded to {course.name} via CSV",
                    status=ActivityStatus.SUCCESS,
                    metadata={
                        'total_rows': upload_result.total_rows,
                        'valid_rows': upload_result.valid_rows,
                        'invalid_rows': upload_result.invalid_rows,
                        'duplicate_rows': upload_result.duplicate_rows,
                        'created_learners': upload_result.created_learners,
                        'enrollment_success': upload_result.enrollment_success,
                        'enrollment_failed': upload_result.enrollment_failed
                    }
                )
            except Exception as log_error:
                logger.warning(f"Failed to log bulk upload activity: {log_error}")
            
            return {
                'ok': True,
                'status': 200,
                'data': upload_result.dict()
            }
            
        except Exception as e:
            logger.error(f"Error uploading learners CSV directly: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _parse_and_validate_csv(self, csv_content: bytes, course_id: str) -> CSVValidationResult:
        """Parse and validate CSV content."""
        valid_rows = []
        invalid_rows = []
        duplicate_rows = []
        seen_emails = set()
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content.decode('utf-8')))
            
            max_rows = int(os.getenv('MAX_CSV_ROWS', 5000))
            row_count = 0
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                row_count += 1
                
                if row_count > max_rows:
                    invalid_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': [f'CSV exceeds maximum {max_rows} rows']
                    })
                    break
                
                # Validate required fields
                errors = []
                if not row.get('name', '').strip():
                    errors.append('Name is required')
                if not row.get('email', '').strip():
                    errors.append('Email is required')
                if not row.get('organization_website', '').strip():
                    errors.append('Organization website is required')
                
                # Validate email format
                email = row.get('email', '').strip()
                if email and '@' not in email:
                    errors.append('Invalid email format')
                
                # Check for duplicates within CSV
                if email in seen_emails:
                    duplicate_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': ['Duplicate email in CSV']
                    })
                    continue
                seen_emails.add(email)
                
                # Check if organization exists
                org_website = row.get('organization_website', '').strip()
                if org_website:
                    org = self.db.get_organization_by_website(org_website)
                    if not org:
                        errors.append(f'Organization {org_website} not found')
                
                # Check if learner already exists
                if email and not errors:
                    existing_learner = self.db.get_learner_by_course_and_email(course_id, email)
                    if existing_learner:
                        errors.append('Learner already enrolled in this course')
                
                if errors:
                    invalid_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': errors
                    })
                else:
                    try:
                        valid_rows.append(LearnerCSVRow(
                            name=row['name'].strip(),
                            email=email,
                            organization_website=org_website
                        ))
                    except Exception as e:
                        invalid_rows.append({
                            'row_number': row_num,
                            'row_data': row,
                            'errors': [f'Validation error: {str(e)}']
                        })
            
            return CSVValidationResult(
                valid_rows=valid_rows,
                invalid_rows=invalid_rows,
                duplicate_rows=duplicate_rows
            )
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            return CSVValidationResult(
                valid_rows=[],
                invalid_rows=[{
                    'row_number': 1,
                    'row_data': {},
                    'errors': [f'CSV parsing error: {str(e)}']
                }],
                duplicate_rows=[]
            )

    def _parse_and_validate_csv_direct(self, csv_data: str, course_id: str) -> CSVValidationResult:
        """Parse and validate CSV data directly from string."""
        valid_rows = []
        invalid_rows = []
        duplicate_rows = []
        seen_emails = set()
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_data))
            
            max_rows = int(os.getenv('MAX_CSV_ROWS', 5000))
            row_count = 0
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                row_count += 1
                
                if row_count > max_rows:
                    invalid_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': [f'CSV exceeds maximum allowed rows ({max_rows})']
                    })
                    continue
                
                # Validate required fields
                errors = []
                if not row.get('name', '').strip():
                    errors.append('name is required')
                if not row.get('email', '').strip():
                    errors.append('email is required')
                if not row.get('organization_website', '').strip():
                    errors.append('organization_website is required')
                
                if errors:
                    invalid_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': errors
                    })
                    continue
                
                # Check for duplicates
                email = row['email'].strip().lower()
                if email in seen_emails:
                    duplicate_rows.append({
                        'row_number': row_num,
                        'row_data': row
                    })
                    continue
                
                seen_emails.add(email)
                
                # Create learner row
                try:
                    learner_row = LearnerCSVRow(
                        name=row['name'].strip(),
                        email=row['email'].strip(),
                        organization_website=row['organization_website'].strip()
                    )
                    valid_rows.append(learner_row)
                except Exception as e:
                    invalid_rows.append({
                        'row_number': row_num,
                        'row_data': row,
                        'errors': [f'Validation error: {str(e)}']
                    })
            
            return CSVValidationResult(
                valid_rows=valid_rows,
                invalid_rows=invalid_rows,
                duplicate_rows=duplicate_rows
            )
            
        except Exception as e:
            logger.error(f"Error parsing CSV data: {e}")
            return CSVValidationResult(
                valid_rows=[],
                invalid_rows=[{
                    'row_number': 1,
                    'row_data': {},
                    'errors': [f'CSV parsing error: {str(e)}']
                }],
                duplicate_rows=[]
            )

    def _process_learner_enrollments(self, validation_result: CSVValidationResult, course_id: str) -> UploadResult:
        """Process learner enrollments."""
        created_learners = 0
        enrollment_success = 0
        enrollment_failed = 0
        enrollment_errors = []
        
        for learner_row in validation_result.valid_rows:
            try:
                # Create learner record
                learner = self.db.create_learner_if_not_exists({
                    'name': learner_row.name,
                    'email': learner_row.email,
                    'organization_website': learner_row.organization_website,
                    'course_id': course_id
                })
                
                if learner:
                    created_learners += 1
                    
                    # Enroll in Graphy
                    enrollment_request = GraphyEnrollmentRequest(
                        course_id=course_id,
                        email=learner_row.email,
                        name=learner_row.name,
                        metadata={
                            'organization_website': learner_row.organization_website
                        }
                    )
                    
                    enrollment_response = self.graphy.enroll_learner(enrollment_request)
                    
                    if enrollment_response.ok:
                        # Update learner with enrollment details
                        self.db.update_learner(learner.id, {
                            'enrollment_status': 'enrolled'
                        })
                        enrollment_success += 1
                    else:
                        # Mark enrollment failed
                        self.db.update_learner(learner.id, {
                            'enrollment_error': enrollment_response.error
                        })
                        enrollment_failed += 1
                        enrollment_errors.append(EnrollmentResult(
                            learner_email=learner_row.email,
                            success=False,
                            error=enrollment_response.error
                        ))
                
            except Exception as e:
                logger.error(f"Error processing learner {learner_row.email}: {e}")
                enrollment_failed += 1
                enrollment_errors.append(EnrollmentResult(
                    learner_email=learner_row.email,
                    success=False,
                    error=str(e)
                ))
        
        return UploadResult(
            total_rows=len(validation_result.valid_rows) + len(validation_result.invalid_rows) + len(validation_result.duplicate_rows),
            valid_rows=len(validation_result.valid_rows),
            invalid_rows=len(validation_result.invalid_rows),
            duplicate_rows=len(validation_result.duplicate_rows),
            created_learners=created_learners,
            enrollment_success=enrollment_success,
            enrollment_failed=enrollment_failed,
            validation_errors=validation_result.invalid_rows,
            enrollment_errors=enrollment_errors
        )

    def _handle_preview_certificate(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle PREVIEW_CERTIFICATE action."""
        try:
            # Validate payload
            preview_data = PreviewCertificatePayload(**payload)
            
            # Get course
            course = self.db.get_course_by_course_id(preview_data.course_id)
            if not course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {preview_data.course_id} not found'
                    }
                }
            
            # Get organization
            org = self.db.get_organization_by_website(preview_data.organization_website)
            if not org:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'ORGANIZATION_NOT_FOUND',
                        'message': f'Organization {preview_data.organization_website} not found'
                    }
                }
            
            # Create preview context
            context = CertificateContext(
                learner_name=preview_data.learner_name,
                course_name=course.name,
                completion_date=datetime.utcnow().isoformat() + 'Z',
                organization=org.name or org.website,
                learner_email=preview_data.learner_email
            )
            
            # Generate preview
            preview_html = self.renderer.preview_certificate(course.certificate_template_html, context)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'preview_html': preview_html
                }
            }
            
        except Exception as e:
            logger.error(f"Error previewing certificate: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_list_courses(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_COURSES action."""
        try:
            # Validate payload
            list_data = ListCoursesPayload(**payload)
            
            # Get courses
            courses, total_count = self.db.list_courses(list_data.limit, list_data.offset, list_data.search)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'courses': [json.loads(course.json()) for course in courses]
                },
                'pagination': {
                    'total': total_count,
                    'limit': list_data.limit,
                    'offset': list_data.offset,
                    'has_more': (list_data.offset + len(courses)) < total_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing courses: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_view_learners(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle VIEW_LEARNERS action."""
        try:
            # Validate payload
            view_data = ViewLearnersPayload(**payload)
            
            # Check if course exists
            course = self.db.get_course_by_course_id(view_data.course_id)
            if not course:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'COURSE_NOT_FOUND',
                        'message': f'Course with ID {view_data.course_id} not found'
                    }
                }
            
            # Get learners
            learners = self.db.query_learners_for_course(view_data.course_id, view_data.limit, view_data.offset)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'learners': [json.loads(learner.json()) for learner in learners]
                }
            }
            
        except Exception as e:
            logger.error(f"Error viewing learners: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_list_all_learners(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_ALL_LEARNERS action with grouped response."""
        try:
            # Validate payload
            list_data = ListAllLearnersPayload(**payload)
            
            # Get all learners (we'll group them by email)
            all_learners = []
            
            if list_data.organization_website and list_data.course_id:
                # Both filters
                learners = self.db.query_learners_for_org(
                    list_data.organization_website, 
                    list_data.limit * 10,  # Get more to account for grouping
                    list_data.offset,
                    list_data.search
                )
                learners = [l for l in learners if l.course_id == list_data.course_id]
                all_learners = learners
            elif list_data.organization_website:
                # Filter by organization only
                all_learners = self.db.query_learners_for_org(
                    list_data.organization_website, 
                    list_data.limit * 10,  # Get more to account for grouping
                    list_data.offset,
                    list_data.search
                )
            elif list_data.course_id:
                # Filter by course only
                all_learners = self.db.query_learners_for_course(
                    list_data.course_id, 
                    list_data.limit * 10,  # Get more to account for grouping
                    list_data.offset,
                    list_data.search
                )
            else:
                # No filters - get all learners from database
                # This ensures we get both learners with valid organizations and learners without valid organizations
                all_learners = []
                
                try:
                    from appwrite.query import Query
                    queries = [
                        Query.limit(1000),
                        Query.offset(0),
                        Query.order_desc('$createdAt')
                    ]
                    
                    # Get all learners first (no search filter at database level for wildcard search)
                    result = self.db.databases.list_documents(
                        database_id='main',
                        collection_id='learners',
                        queries=queries
                    )
                    
                    for doc in result['documents']:
                        learner = self.db._convert_document_to_model(doc, LearnerModel)
                        if learner:
                            all_learners.append(learner)
                    
                    # Apply wildcard search filter in Python if provided (search across name, email, and organization_website)
                    if list_data.search:
                        search_term = list_data.search.lower()
                        all_learners = [
                            learner for learner in all_learners
                            if (search_term in learner.name.lower() or 
                                search_term in learner.email.lower() or 
                                search_term in learner.organization_website.lower())
                        ]
                            
                    logger.info(f"Found {len(all_learners)} learners from database with search: {list_data.search}")
                except Exception as e:
                    logger.error(f"Error getting learners from database: {e}")
                    all_learners = []
            
            # Group learners by email
            learner_groups = {}
            for learner in all_learners:
                email = learner.email
                if email not in learner_groups:
                    learner_groups[email] = {
                        'learner_info': {
                            'name': learner.name,
                            'email': learner.email,
                            'organization_website': learner.organization_website
                        },
                        'organization_info': None,  # Will be populated below
                        'courses': []
                    }
                
                # Get course information
                course = self.db.get_course_by_course_id(learner.course_id)
                course_name = course.name if course else f"Course {learner.course_id}"
                
                # Add course info
                completion_date = getattr(learner, 'completion_date', None)
                created_at = getattr(learner, 'created_at', None)
                
                # If completion_date is not null, set completion_percentage to 100
                completion_percentage = getattr(learner, 'completion_percentage', 0)
                if completion_date is not None:
                    completion_percentage = completion_percentage
                
                course_info = {
                    'course_id': learner.course_id,
                    'course_name': course_name,
                    'enrollment_status': getattr(learner, 'enrollment_status', 'pending'),
                    'completion_percentage': completion_percentage,
                    'completion_date': completion_date.isoformat() if completion_date else None,
                    'certificate_status': 'Issued' if completion_date else 'Pending' if getattr(learner, 'enrollment_status', 'pending') == 'completed' else 'N/A',
                    'created_at': created_at.isoformat() if created_at else None
                }
                learner_groups[email]['courses'].append(course_info)
            
            # Get organization info for each unique organization
            org_websites = set(group['learner_info']['organization_website'] for group in learner_groups.values() if group['learner_info']['organization_website'])
            organizations = {}
            for website in org_websites:
                org = self.db.get_organization_by_website(website)
                if org:
                    organizations[website] = {
                        'name': org.name,
                        'website': org.website,
                        'sop_email': org.sop_email,
                        'created_at': org.created_at.isoformat() if org.created_at else None
                    }
            
            # Populate organization info and format response
            grouped_learners = []
            for email, group in learner_groups.items():
                org_website = group['learner_info']['organization_website']
                
                if org_website and org_website in organizations:
                    # Organization exists
                    group['organization_info'] = organizations[org_website]
                elif org_website:
                    # Organization website exists but organization not found
                    group['organization_info'] = {
                        'name': 'Organization Not Found',
                        'website': org_website,
                        'sop_email': None,
                        'created_at': None
                    }
                else:
                    # No organization website (null/None)
                    group['organization_info'] = {
                        'name': 'No Organization',
                        'website': None,
                        'sop_email': None,
                        'created_at': None
                    }
                
                # Sort courses by creation date (handle None values)
                group['courses'].sort(key=lambda x: x['created_at'] or '1900-01-01T00:00:00', reverse=True)
                grouped_learners.append(group)
            
            # Sort learners by name
            grouped_learners.sort(key=lambda x: x['learner_info']['name'])
            
            # Apply pagination to grouped results
            start_idx = list_data.offset
            end_idx = start_idx + list_data.limit
            paginated_learners = grouped_learners[start_idx:end_idx]
            
            # Calculate summary statistics
            total_learners = len(grouped_learners)
            active_learners = len([l for l in grouped_learners if any(c['enrollment_status'] in ['enrolled', 'in_progress'] for c in l['courses'])])
            total_enrollments = sum(len(l['courses']) for l in grouped_learners)
            completed_courses = sum(len([c for c in l['courses'] if c['enrollment_status'] == 'completed']) for l in grouped_learners)
            completion_rate = round((completed_courses / total_enrollments * 100) if total_enrollments > 0 else 0, 1)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'learners': paginated_learners,
                    'summary': {
                        'total_learners': total_learners,
                        'active_learners': active_learners,
                        'total_enrollments': total_enrollments,
                        'completion_rate': completion_rate
                    },
                    'pagination': {
                        'total': total_learners,
                        'limit': list_data.limit,
                        'offset': list_data.offset,
                        'has_more': end_idx < total_learners
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing all learners: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_add_organization(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle ADD_ORGANIZATION action."""
        try:
            # Validate payload
            org_data = AddOrganizationPayload(**payload)
            
            # Check if organization already exists
            existing_org = self.db.get_organization_by_website(org_data.website)
            if existing_org:
                return {
                    'ok': False,
                    'status': 409,
                    'error': {
                        'code': 'ORGANIZATION_EXISTS',
                        'message': f'Organization with website {org_data.website} already exists'
                    }
                }
            
            # Create SOP user in Appwrite's built-in auth table FIRST
            # This ensures we don't create an organization without a valid SOP user
            sop_user_created = False
            sop_user_result = None
            
            try:
                sop_user_result = self.auth.create_user_in_appwrite(
                    email=org_data.sop_email,
                    password=org_data.sop_password,
                    name=org_data.name or f"SOP User for {org_data.website}",
                    role='sop',
                    organization_website=org_data.website
                )
                
                if sop_user_result and sop_user_result.get('ok'):
                    sop_user_created = True
                    logger.info(f"SOP user created successfully for organization {org_data.website}")
                else:
                    error_msg = sop_user_result.get('error', 'Unknown error') if sop_user_result else 'No response from auth service'
                    logger.error(f"Failed to create SOP user for organization {org_data.website}: {error_msg}")
                    return {
                        'ok': False,
                        'status': 500,
                        'error': {
                            'code': 'SOP_USER_CREATION_FAILED',
                            'message': f'Failed to create SOP user: {error_msg}'
                        }
                    }
                    
            except Exception as sop_error:
                logger.error(f"Error creating SOP user for organization {org_data.website}: {sop_error}")
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'SOP_USER_CREATION_ERROR',
                        'message': f'Error creating SOP user: {str(sop_error)}'
                    }
                }
            
            # Only create organization if SOP user was created successfully
            org = self.db.create_organization({
                'website': org_data.website,
                'name': org_data.name,
                'sop_email': org_data.sop_email
            })
            
            if not org:
                # If organization creation fails after SOP user was created,
                # we should clean up the SOP user (though this is complex with Appwrite)
                logger.error(f"Failed to create organization after SOP user was created for {org_data.website}")
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'ORGANIZATION_CREATION_FAILED',
                        'message': 'Failed to create organization after SOP user was created'
                    }
                }
            
            # Log activity (with error handling to not break main functionality)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_ADDED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=org_data.name or org_data.website,
                    organization_website=org_data.website,
                    details=f"Organization {org_data.name or org_data.website} created with SOP user {org_data.sop_email}",
                    status=ActivityStatus.SUCCESS,
                    metadata={
                        'sop_user_created': sop_user_created,
                        'sop_email': org_data.sop_email
                    }
                )
            except Exception as log_error:
                logger.warning(f"Failed to log organization creation activity: {log_error}")
            
            return {
                'ok': True,
                'status': 201,
                'data': {
                    'organization': json.loads(org.json()),
                    'sop_user_created': sop_user_created,
                    'message': 'Organization created successfully. SOP user credentials have been set up.' if sop_user_created else 'Organization created successfully. SOP user creation failed - please create manually.'
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding organization: {e}")
            
            # Log failed activity (with error handling)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_ADDED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=payload.get('name', 'Unknown Organization'),
                    organization_website=payload.get('website'),
                    details=f"Organization creation failed: {str(e)}",
                    status=ActivityStatus.FAILED,
                    error_message=str(e)
                )
            except Exception as log_error:
                logger.warning(f"Failed to log organization creation failure activity: {log_error}")
            
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_edit_organization(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle EDIT_ORGANIZATION action."""
        try:
            # Validate payload
            org_data = EditOrganizationPayload(**payload)
            
            # Check if organization exists by ID
            existing_org = self.db.get_organization_by_id(org_data.organization_id)
            if not existing_org:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'ORGANIZATION_NOT_FOUND',
                        'message': f'Organization with ID {org_data.organization_id} not found'
                    }
                }
            
            # Prepare update data
            update_data = {}
            old_website = existing_org.website
            learners_updated = 0
            
            if org_data.website is not None:
                update_data['website'] = org_data.website
            if org_data.name is not None:
                update_data['name'] = org_data.name
            if org_data.sop_email is not None:
                update_data['sop_email'] = org_data.sop_email
            
            # Update organization by ID
            updated_org = self.db.update_organization_by_id(org_data.organization_id, update_data)
            
            if not updated_org:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'UPDATE_FAILED',
                        'message': 'Failed to update organization'
                    }
                }
            
            # If website was changed, update all learners and SOP user with the old website
            if org_data.website is not None and org_data.website != old_website:
                learners_updated = self.db.update_learners_organization_website(old_website, org_data.website)
                sop_user_updated = self.db.update_sop_user_organization_website(old_website, org_data.website)
                logger.info(f"Updated {learners_updated} learners and {sop_user_updated} SOP user from {old_website} to {org_data.website}")
            else:
                sop_user_updated = 0
                
                # Log activity (with error handling to not break main functionality)
                try:
                    self.activity_log.log_activity(
                        activity_type=ActivityType.ORGANIZATION_UPDATED,
                        actor="Admin User",
                        actor_email=None,
                        actor_role=auth_context.role.value,
                        target=updated_org.name or updated_org.website,
                        organization_website=updated_org.website,
                        details=f"Organization {updated_org.name or updated_org.website} updated. {learners_updated} learners and {sop_user_updated} SOP user updated.",
                        status=ActivityStatus.SUCCESS,
                        metadata={
                            'learners_updated': learners_updated,
                            'sop_user_updated': sop_user_updated,
                            'old_website': old_website if org_data.website != old_website else None
                        }
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log organization update activity: {log_error}")
                
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'organization': json.loads(updated_org.json()),
                        'learners_updated': learners_updated,
                        'sop_user_updated': sop_user_updated,
                        'message': f'Organization updated successfully. {learners_updated} learners and {sop_user_updated} SOP user updated with new website.' if learners_updated > 0 or sop_user_updated > 0 else 'Organization updated successfully.'
                    }
                }
            
        except Exception as e:
            logger.error(f"Error editing organization: {e}")
            
            # Log failed activity (with error handling)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_UPDATED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=payload.get('name', 'Unknown Organization'),
                    organization_website=payload.get('website'),
                    details=f"Organization update failed: {str(e)}",
                    status=ActivityStatus.FAILED,
                    error_message=str(e)
                )
            except Exception as log_error:
                logger.warning(f"Failed to log organization update failure activity: {log_error}")
            
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_delete_organization(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle DELETE_ORGANIZATION action."""
        try:
            # Validate payload
            org_data = DeleteOrganizationPayload(**payload)
            
            # Check if organization exists
            existing_org = self.db.get_organization_by_website(org_data.website)
            if not existing_org:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'ORGANIZATION_NOT_FOUND',
                        'message': f'Organization with website {org_data.website} not found'
                    }
                }
            
            # Delete organization
            success = self.db.delete_organization(org_data.website)
            
            if not success:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'DELETE_FAILED',
                        'message': 'Failed to delete organization'
                    }
                }
            
            # Log activity (with error handling to not break main functionality)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_DELETED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=existing_org.name or existing_org.website,
                    organization_website=existing_org.website,
                    details=f"Organization {existing_org.name or existing_org.website} deleted",
                    status=ActivityStatus.SUCCESS,
                    metadata={
                        'sop_email': existing_org.sop_email
                    }
                )
            except Exception as log_error:
                logger.warning(f"Failed to log organization deletion activity: {log_error}")
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Organization {org_data.website} deleted successfully'
                }
            }
            
        except Exception as e:
            logger.error(f"Error deleting organization: {e}")
            
            # Log failed activity (with error handling)
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_DELETED,
                    actor="Admin User",
                    actor_email=None,
                    actor_role=auth_context.role.value,
                    target=payload.get('name', 'Unknown Organization'),
                    organization_website=payload.get('website'),
                    details=f"Organization deletion failed: {str(e)}",
                    status=ActivityStatus.FAILED,
                    error_message=str(e)
                )
            except Exception as log_error:
                logger.warning(f"Failed to log organization deletion failure activity: {log_error}")
            
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_list_organizations(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_ORGANIZATIONS action."""
        try:
            # Validate payload
            list_data = ListOrganizationsPayload(**payload)
            
            # Get organizations from database
            organizations, total_count = self.db.list_organizations(list_data.limit, list_data.offset, list_data.search)
            
            # Convert to JSON-serializable format
            orgs_data = []
            for org in organizations:
                org_dict = json.loads(org.json())
                orgs_data.append(org_dict)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'organizations': orgs_data
                },
                'pagination': {
                    'total': total_count,
                    'limit': list_data.limit,
                    'offset': list_data.offset,
                    'has_more': (list_data.offset + len(orgs_data)) < total_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing organizations: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'DATABASE_ERROR',
                    'message': f'Failed to list organizations: {str(e)}'
                }
            }

    def _handle_reset_sop_password(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle RESET_SOP_PASSWORD action."""
        try:
            # Validate payload
            reset_data = ResetSOPPasswordPayload(**payload)
            
            # Reset SOP user password directly using email
            reset_result = self.auth.reset_user_password(reset_data.sop_email, reset_data.new_password)
            
            if not reset_result.get('ok'):
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'PASSWORD_RESET_FAILED',
                        'message': f'Failed to reset password: {reset_result.get("error")}'
                    }
                }
            
            # Get organization info for logging (optional)
            org = None
            try:
                # Try to find organization by SOP email for logging purposes
                orgs = self.db.list_organizations(limit=1000, offset=0)
                for o in orgs:
                    if o.sop_email == reset_data.sop_email:
                        org = o
                        break
            except Exception as e:
                logger.warning(f"Could not find organization for SOP email {reset_data.sop_email}: {e}")
            
            # Log activity
            try:
                self.activity_log.log_activity(
                    activity_type=ActivityType.ORGANIZATION_UPDATED,
                    actor="Admin User",
                    actor_email=auth_context.email,
                    actor_role=auth_context.role.value,
                    target=org.name if org else reset_data.sop_email,
                    organization_website=org.website if org else None,
                    details=f"SOP password reset for {reset_data.sop_email}",
                    status=ActivityStatus.SUCCESS,
                    metadata={
                        'sop_email': reset_data.sop_email,
                        'action': 'password_reset'
                    }
                )
                logger.info(f"Activity logged: SOP password reset for {reset_data.sop_email}")
            except Exception as e:
                logger.warning(f"Failed to log password reset activity: {e}")
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'SOP password reset successfully for {reset_data.sop_email}',
                    'sop_email': reset_data.sop_email,
                    'organization_website': org.website if org else None,
                    'organization_name': org.name if org else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error resetting SOP password: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': f'Internal server error: {str(e)}'
                }
            }

    def _handle_resend_certificate(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle RESEND_CERTIFICATE action (SOP-initiated)."""
        try:
            # Validate payload
            resend_data = ResendCertificatePayload(**payload)

            # Get learner
            learner = None
            if resend_data.learner_email and resend_data.course_id:
                learner = self.db.get_learner_by_course_and_email(
                    resend_data.course_id,
                    str(resend_data.learner_email)
                )

            else:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_PAYLOAD',
                        'message': 'Either learner_email+course_id or organization_website must be provided'
                    }
                }

            # Handle single learner resend
            if learner:

                # Create webhook event for certificate resend
                webhook_data = {
                    'event_id': f'resend_{learner.email}_{resend_data.course_id}_{int(datetime.utcnow().timestamp())}',
                    'learner_email': learner.email,
                    'course_id': resend_data.course_id,
                    'completion_date': learner.completion_date.isoformat().replace('+00:00', 'Z') if learner.completion_date else datetime.utcnow().isoformat().replace('+00:00', 'Z'),
                    'status': 'pending',
                    'created_at': datetime.utcnow().isoformat().replace('+00:00', 'Z')
                }

                webhook_event = self.db.create_webhook_event(webhook_data)
                if not webhook_event:
                    return {
                        'ok': False,
                        'status': 500,
                        'error': {
                            'code': 'WEBHOOK_CREATION_FAILED',
                            'message': 'Failed to create webhook event for certificate resend'
                        }
                    }

                webhook_event_id = webhook_event.id
                logger.info(f"Created webhook event {webhook_event_id} for certificate resend")

                # Immediately trigger certificate generation
                logger.info(f"Triggering immediate certificate generation for resend: {learner.email}")
                cert_result = self.trigger_certificate_generation(webhook_event_id)

                if cert_result.get('ok'):
                    logger.info(f"Certificate resend triggered successfully for {learner.email}")
                    # Update learner status
                    self.db.update_learner(learner.id, {
                        'certificate_send_status': 'sent',
                        # 'last_resend_attempt': datetime.utcnow().isoformat() + 'Z'
                    })

                    # Log activity for certificate resending
                    try:
                        course = self.db.get_course_by_course_id(resend_data.course_id)
                        org = self.db.get_organization_by_website(learner.organization_website)
                        course_name = course.name if course else "Unknown Course"
                        org_name = org.name if org else learner.organization_website
                        
                        self.activity_log.log_activity(
                            activity_type=ActivityType.CERTIFICATE_RESENT,
                            actor="Admin User",
                            actor_email=auth_context.email,
                            actor_role=auth_context.role.value,
                            target=learner.name,
                            target_email=learner.email,
                            organization_website=learner.organization_website,
                            course_id=resend_data.course_id,
                            details=f"Certificate resent for {learner.name} ({learner.email}) - Course: {course_name}",
                            status=ActivityStatus.SUCCESS,
                            metadata={
                                'webhook_event_id': webhook_event_id,
                                'organization_name': org_name
                            }
                        )
                        logger.info(f"Activity logged: Certificate resent for {learner.email}")
                    except Exception as e:
                        logger.warning(f"Failed to log certificate resent activity: {e}")

                    return {
                        'ok': True,
                        'status': 200,
                        'data': {
                            'message': f'Certificate resent successfully for {learner.email}',
                            'learner_email': learner.email,
                            'course_id': resend_data.course_id,
                            'webhook_event_id': webhook_event_id
                        }
                    }
                else:
                    logger.error(f"Certificate resend failed for {learner.email}: {cert_result.get('error')}")
                    return {
                        'ok': False,
                        'status': 500,
                        'error': {
                            'code': 'CERTIFICATE_GENERATION_FAILED',
                            'message': f'Certificate resend failed: {cert_result.get("error")}'
                        }
                    }

            # Handle organization-wide resend
            elif resend_data.organization_website:

                # Get organization
                org = self.db.get_organization_by_website(resend_data.organization_website)
                if not org:
                    return {
                        'ok': False,
                        'status': 404,
                        'error': {
                            'code': 'ORGANIZATION_NOT_FOUND',
                            'message': f'Organization {resend_data.organization_website} not found'
                        }
                    }

                # Get learners for organization
                learners = self.db.query_learners_for_org(resend_data.organization_website)
                learners_to_resend = [
                    l for l in learners
                    if l.completion_at and l.certificate_send_status in ['sent', 'failed']
                ]

                if not learners_to_resend:
                    return {
                        'ok': False,
                        'status': 404,
                        'error': {
                            'code': 'NO_LEARNERS_TO_RESEND',
                            'message': 'No completed learners found for certificate resend'
                        }
                    }

                # Process each learner for certificate resend
                resend_count = 0
                successful_resends = 0
                failed_resends = 0

                for learner in learners_to_resend:
                    try:
                        # Create webhook event for certificate resend
                        webhook_data = {
                            'event_id': f'resend_{learner.email}_{learner.course_id}_{int(datetime.utcnow().timestamp())}',
                            'learner_email': learner.email,
                            'course_id': learner.course_id,
                            'completion_date': learner.completion_date.isoformat().replace('+00:00', 'Z') if learner.completion_date else datetime.utcnow().isoformat().replace('+00:00', 'Z'),
                            'status': 'pending',
                            'created_at': datetime.utcnow().isoformat().replace('+00:00', 'Z')
                        }

                        webhook_event = self.db.create_webhook_event(webhook_data)
                        if webhook_event:
                            webhook_event_id = webhook_event.id
                            logger.info(f"Created webhook event {webhook_event_id} for certificate resend: {learner.email}")

                            # Immediately trigger certificate generation
                            cert_result = self.trigger_certificate_generation(webhook_event_id)

                            if cert_result.get('ok'):
                                logger.info(f"Certificate resend triggered successfully for {learner.email}")
                                # Update learner status
                                self.db.update_learner(learner.id, {
                                    'certificate_send_status': 'sent',
                                    'last_resend_attempt': datetime.utcnow().isoformat() + 'Z'
                                })
                                
                                # Log activity for certificate resending
                                try:
                                    course = self.db.get_course_by_course_id(learner.course_id)
                                    org = self.db.get_organization_by_website(learner.organization_website)
                                    course_name = course.name if course else "Unknown Course"
                                    org_name = org.name if org else learner.organization_website
                                    
                                    self.activity_log.log_activity(
                                        activity_type=ActivityType.CERTIFICATE_RESENT,
                                        actor="Admin User",
                                        actor_email=auth_context.email,
                                        actor_role=auth_context.role.value,
                                        target=learner.name,
                                        target_email=learner.email,
                                        organization_website=learner.organization_website,
                                        course_id=learner.course_id,
                                        details=f"Certificate resent for {learner.name} ({learner.email}) - Course: {course_name} (Organization-wide resend)",
                                        status=ActivityStatus.SUCCESS,
                                        metadata={
                                            'webhook_event_id': webhook_event_id,
                                            'organization_name': org_name,
                                            'organization_wide_resend': True
                                        }
                                    )
                                    logger.info(f"Activity logged: Certificate resent for {learner.email}")
                                except Exception as e:
                                    logger.warning(f"Failed to log certificate resent activity: {e}")
                                
                                successful_resends += 1
                            else:
                                logger.error(f"Certificate resend failed for {learner.email}: {cert_result.get('error')}")
                                failed_resends += 1
                        else:
                            logger.error(f"Failed to create webhook event for {learner.email}")
                            failed_resends += 1

                        resend_count += 1

                    except Exception as e:
                        logger.error(f"Error processing resend for {learner.email}: {e}")
                        failed_resends += 1
                        resend_count += 1

                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'message': f'Certificate resend processed for {resend_count} learners: {successful_resends} successful, {failed_resends} failed',
                        'organization_website': resend_data.organization_website,
                        'total_processed': resend_count,
                        'successful_resends': successful_resends,
                        'failed_resends': failed_resends
                    }
                }

            else:
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_PAYLOAD',
                        'message': 'Invalid resend request parameters'
                    }
                }

        except Exception as e:
            logger.error(f"Error resending certificate: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }


    def trigger_certificate_generation(self, webhook_event_id: str) -> Dict[str, Any]:
        """Trigger certificate generation by calling the certificate worker function."""
        try:
            logger.info(f"Triggering certificate generation for webhook event: {webhook_event_id}")

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
                logger.info(f"Certificate worker response: {result}")
                return {
                    'ok': True,
                    'response': result
                }
            else:
                logger.error(f"Certificate worker failed with status {response.status_code}: {response.text}")
                return {
                    'ok': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }

        except Exception as e:
            logger.error(f"Error triggering certificate generation: {e}")
            return {
                'ok': False,
                'error': str(e)
            }

    def _handle_list_webhooks(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_WEBHOOKS action."""
        try:
            # Validate payload
            list_data = ListWebhooksPayload(**payload)
            
            # Get webhook events
            webhooks = self.db.list_webhook_events(
                list_data.limit,
                list_data.offset,
                list_data.status
            )
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'webhooks': [webhook.dict() for webhook in webhooks]
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_retry_webhook(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle RETRY_WEBHOOK action."""
        try:
            # Validate payload
            retry_data = RetryWebhookPayload(**payload)
            
            # Get webhook event
            webhook_event = self.db.get_webhook_event(retry_data.webhook_event_id)
            if not webhook_event:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'WEBHOOK_NOT_FOUND',
                        'message': f'Webhook event {retry_data.webhook_event_id} not found'
                    }
                }
            
            # Reset webhook status for retry
            self.db.update_webhook_event(retry_data.webhook_event_id, {
                'status': 'received',
                'attempts': 0
            })
            
            # Trigger certificate worker
            # This would typically invoke the certificate_worker function
            # For now, just return success
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Webhook {retry_data.webhook_event_id} queued for retry'
                }
            }
            
        except Exception as e:
            logger.error(f"Error retrying webhook: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_download_certificate(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle DOWNLOAD_CERTIFICATE action."""
        try:
            # Validate payload
            download_data = DownloadCertificatePayload(**payload)
            
            # Get learner
            learner = self.db.get_learner_by_course_and_email(
                download_data.course_id,
                download_data.learner_email
            )
            
            if not learner:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'LEARNER_NOT_FOUND',
                        'message': f'Learner {download_data.learner_email} not found for course {download_data.course_id}'
                    }
                }
            
            # Check if certificate exists
            if not learner.certificate_file_id:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'CERTIFICATE_NOT_FOUND',
                        'message': 'Certificate not yet generated for this learner'
                    }
                }
            
            # Generate download URL (signed URL for security)
            certificate_bucket_id = os.getenv('CERTIFICATE_BUCKET_ID', 'certificates')
            download_url = self.db.get_file_download_url(
                learner.certificate_file_id,
                certificate_bucket_id
            )
            
            if not download_url:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'DOWNLOAD_URL_ERROR',
                        'message': 'Failed to generate download URL'
                    }
                }
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'download_url': download_url,
                    'filename': f"Certificate_{learner.name}_{download_data.course_id}.pdf",
                    'learner_name': learner.name,
                    'learner_email': learner.email,
                    'course_id': download_data.course_id,
                    'organization_website': learner.organization_website
                }
            }
            
        except Exception as e:
            logger.error(f"Error downloading certificate: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_list_activity_logs(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_ACTIVITY_LOGS action."""
        try:
            # Validate payload
            list_data = ListActivityLogsPayload(**payload)
            
            # Get activity logs
            logs, total_count = self.activity_log.get_activity_logs(
                limit=list_data.limit,
                offset=list_data.offset,
                activity_type=list_data.activity_type,
                status=list_data.status,
                organization_website=list_data.organization_website,
                course_id=list_data.course_id,
                actor=list_data.actor,
                start_date=list_data.start_date,
                end_date=list_data.end_date
            )
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'logs': [json.loads(log.json()) for log in logs]
                },
                'pagination': {
                    'total': total_count,
                    'limit': list_data.limit,
                    'offset': list_data.offset,
                    'has_more': (list_data.offset + len(logs)) < total_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing activity logs: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_learner_statistics(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LEARNER_STATISTICS action."""
        try:
            # Validate payload
            stats_data = LearnerStatisticsPayload(**payload)
            
            # Get all learners across all organizations
            organizations, _ = self.db.list_organizations(limit=1000, offset=0)
            all_learners = []
            
            for org in organizations:
                org_learners = self.db.query_learners_for_org(org.website, limit=10000, offset=0)
                all_learners.extend(org_learners)
            
            # Calculate metrics
            total_learners = len(set(learner.email for learner in all_learners))  # Unique learners
            total_enrollments = len(all_learners)  # Total course enrollments
            
            # Active learners (currently enrolled or in progress)
            active_learners = len(set(
                learner.email for learner in all_learners 
                if getattr(learner, 'enrollment_status', 'pending') in ['enrolled', 'in_progress']
            ))
            
            # Completion rate (average completion percentage)
            completion_percentages = [
                getattr(learner, 'completion_percentage', 0) 
                for learner in all_learners 
                if getattr(learner, 'completion_percentage', 0) is not None
            ]
            avg_completion_rate = round(
                sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0, 
                1
            )
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'total_learners': total_learners,
                    'active_learners': active_learners,
                    'total_enrollments': total_enrollments,
                    'completion_rate': avg_completion_rate
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting learner statistics: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'STATISTICS_ERROR',
                    'message': str(e)
                }
            }

    def _handle_organization_statistics(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle ORGANIZATION_STATISTICS action."""
        try:
            # Validate payload
            stats_data = OrganizationStatisticsPayload(**payload)
            
            # Get all organizations
            organizations, _ = self.db.list_organizations(limit=1000, offset=0)
            
            # Calculate metrics
            total_organizations = len(organizations)
            
            # Active organizations (with websites)
            active_organizations = len([org for org in organizations if org.website and org.website.strip()])
            
            # POC contacts (with POC/SOP emails)
            poc_contacts = len([org for org in organizations if org.sop_email and org.sop_email.strip()])
            
            # Total learners across all organizations
            total_learners = 0
            for org in organizations:
                org_learners = self.db.query_learners_for_org(org.website, limit=10000, offset=0)
                total_learners += len(org_learners)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'total_organizations': total_organizations,
                    'active_organizations': active_organizations,
                    'poc_contacts': poc_contacts,
                    'total_learners': total_learners
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting organization statistics: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'STATISTICS_ERROR',
                    'message': str(e)
                }
            }

    def _handle_course_statistics(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle COURSE_STATISTICS action."""
        try:
            # Validate payload
            stats_data = CourseStatisticsPayload(**payload)
            
            # Get all courses
            courses, _ = self.db.list_courses(limit=1000, offset=0)
            
            # Calculate metrics
            total_courses = len(courses)
            
            # Total learners across all courses
            total_learners = 0
            completion_percentages = []
            
            for course in courses:
                # Get learners for this course
                course_learners = self.db.query_learners_for_course(course.course_id, limit=10000, offset=0)
                total_learners += len(course_learners)
                
                # Collect completion percentages
                for learner in course_learners:
                    completion_pct = getattr(learner, 'completion_percentage', 0)
                    if completion_pct is not None:
                        completion_percentages.append(completion_pct)
            
            # Average completion rate
            avg_completion = round(
                sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0, 
                1
            )
            
            # Certificate templates (courses with templates)
            certificate_templates = len([course for course in courses if course.certificate_template_html and course.certificate_template_html.strip()])
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'total_courses': total_courses,
                    'total_learners': total_learners,
                    'avg_completion': avg_completion,
                    'certificate_templates': certificate_templates
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting course statistics: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'STATISTICS_ERROR',
                    'message': str(e)
                }
            }


def main(context):
    """Main function entry point for Appwrite function."""
    try:
        # Get request data from context
        data = context.req.body
        context.log(f"Raw data received: {data}")
        
        # Parse JSON if provided
        if data:
            try:
                # First parse the outer JSON
                outer_data = json.loads(data)
                logger.info(f"Outer parsed data: {outer_data}")
                
                # Check if there's a 'body' field containing the actual data
                if 'body' in outer_data:
                    # Parse the inner JSON from the body field
                    request_data = json.loads(outer_data['body'])
                    logger.info(f"Inner parsed request_data: {request_data}")
                else:
                    # Use the outer data directly
                    request_data = outer_data
                    logger.info(f"Using outer data as request_data: {request_data}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return context.res.json({
                    "ok": False,
                    "error": f"Invalid JSON: {e}",
                    "message": "Failed to parse request"
                }, 400)
        else:
            # Default to health check if no data provided
            request_data = {"action": "HEALTH_CHECK"}
            logger.info("No data provided, using default health check")
        
        # Initialize router
        router = AdminRouter()
        
        # Handle request
        context.log(f"get into router 1: {str(request_data)}")
        
        # Check if JWT token is in the request data
        jwt_token = request_data.get('jwt_token')
        if jwt_token:
            # Add JWT to headers for authentication
            headers = dict(context.req.headers) if context.req.headers else {}
            headers['Authorization'] = f'Bearer {jwt_token}'
        else:
            headers = context.req.headers
            
        response = router.handle_request(context, request_data, headers=headers)
        
        # Return response
        if hasattr(response, 'to_dict'):
            return context.res.json(response.to_dict())
        else:
            return context.res.json(response)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)
