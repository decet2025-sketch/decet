"""
Admin Router - Main entrypoint for all admin operations.
"""

import csv
import io
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
shared_dir = os.path.join(current_dir, 'shared')
sys.path.insert(0, current_dir)

from shared.models import (
    ActionRequest, ActionType, BaseResponse,
    CreateCoursePayload, EditCoursePayload, DeleteCoursePayload,
    PreviewCertificatePayload, ListCoursesPayload, ViewLearnersPayload,
    AddOrganizationPayload, EditOrganizationPayload, DeleteOrganizationPayload,
    UploadLearnersCSVPayload, UploadLearnersCSVDirectPayload, ResendCertificatePayload, ListWebhooksPayload,
    RetryWebhookPayload, CSVValidationResult, UploadResult, EnrollmentResult,
    CertificateContext, LearnerCSVRow
)
from shared.services.db import AppwriteClient
from shared.services.graphy import GraphyService
from shared.services.email_service_simple import EmailService
from shared.services.renderer import CertificateRenderer
from shared.services.auth import AuthService

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
            
            # Generate JWT token
            token = self.auth.create_jwt_token({
                'user_id': user_id,
                'email': email,
                'role': 'admin',
                'name': name
            })
            
            message = 'Admin user created successfully' if not is_existing else 'Admin user already exists, returning JWT token'
            
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
        """Create an sop user and return JWT token."""
        try:
            email = payload.get('email')
            name = payload.get('name')
            password = payload.get('password')
            organization_website = payload.get('organization_website')

            if not all([email, name, password, organization_website]):
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'MISSING_FIELDS',
                        'message': 'email, name, password, and organization_website are required'
                    }
                }

            # Create user in Appwrite Users collection
            user_result = self.auth.create_user_in_appwrite(
                email=email,
                password=password,
                name=name,
                role='sop',
                organization_website=organization_website
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

            # Generate JWT token
            token = self.auth.create_jwt_token({
                'user_id': user_id,
                'email': email,
                'role': 'sop',
                'name': name,
                'organization_website': organization_website
            })

            message = 'sop user created successfully' if not is_existing else 'sop user already exists, returning JWT token'

            return {
                'ok': True,
                'status': 201 if not is_existing else 200,
                'data': {
                    'user_id': user_id,
                    'email': email,
                    'name': name,
                    'role': 'sop',
                    'token': token,
                    'message': message,
                    'existing': is_existing
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
                ActionType.ADD_ORGANIZATION: self._handle_add_organization,
                ActionType.EDIT_ORGANIZATION: self._handle_edit_organization,
                ActionType.DELETE_ORGANIZATION: self._handle_delete_organization,
                ActionType.RESEND_CERTIFICATE: self._handle_resend_certificate,
                ActionType.LIST_WEBHOOKS: self._handle_list_webhooks,
                ActionType.RETRY_WEBHOOK: self._handle_retry_webhook,
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
            logger.error(f"Error handling admin request: {e}")
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
            
            # Check if course already exists
            existing_course = self.db.get_course_by_course_id(course_data.course_id)
            if existing_course:
                return {
                    'ok': False,
                    'status': 409,
                    'error': {
                        'code': 'COURSE_EXISTS',
                        'message': f'Course with ID {course_data.course_id} already exists'
                    }
                }
            
            # Create course
            course = self.db.create_course({
                'course_id': course_data.course_id,
                'name': course_data.name,
                'certificate_template_html': course_data.certificate_template_html
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
            
            return {
                'ok': True,
                'status': 201,
                'data': {
                    'course': json.loads(course.json())
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating course: {e}")
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
                    enrollment_request = {
                        'course_id': course_id,
                        'email': learner_row.email,
                        'name': learner_row.name,
                        'metadata': {
                            'organization_website': learner_row.organization_website
                        }
                    }
                    
                    enrollment_response = self.graphy.enroll_learner(enrollment_request)
                    
                    if enrollment_response.ok:
                        # Update learner with enrollment details
                        self.db.update_learner(learner.id, {
                            'graphy_enrollment_id': enrollment_response.enrollment_id,
                            'enrolled_at': datetime.utcnow().isoformat() + 'Z'
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
            courses = self.db.list_courses(list_data.limit, list_data.offset)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'courses': [json.loads(course.json()) for course in courses]
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
            
            # Create organization
            org = self.db.create_organization({
                'website': org_data.website,
                'name': org_data.name,
                'sop_email': org_data.sop_email
            })
            
            if not org:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'CREATE_FAILED',
                        'message': 'Failed to create organization'
                    }
                }
            
            return {
                'ok': True,
                'status': 201,
                'data': {
                    'organization':  json.loads(org.json())
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding organization: {e}")
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
            
            # Prepare update data
            update_data = {}
            if org_data.name is not None:
                update_data['name'] = org_data.name
            if org_data.sop_email is not None:
                update_data['sop_email'] = org_data.sop_email
            
            # Update organization
            updated_org = self.db.update_organization(org_data.website, update_data)
            
            if not updated_org:
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'UPDATE_FAILED',
                        'message': 'Failed to update organization'
                    }
                }
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'organization': json.loads(updated_org.json())
                }
            }
            
        except Exception as e:
            logger.error(f"Error editing organization: {e}")
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
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Organization {org_data.website} deleted successfully'
                }
            }
            
        except Exception as e:
            logger.error(f"Error deleting organization: {e}")
            return {
                'ok': False,
                'status': 400,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e)
                }
            }

    def _handle_resend_certificate(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle RESEND_CERTIFICATE action."""
        try:
            # Validate payload
            resend_data = ResendCertificatePayload(**payload)
            
            # Find learners to resend certificates for
            learners = []
            if resend_data.learner_email:
                # Find specific learner
                if resend_data.course_id:
                    learner = self.db.get_learner_by_course_and_email(resend_data.course_id, resend_data.learner_email)
                    if learner:
                        learners = [learner]
                else:
                    # Find learner across all courses
                    # This would require a more complex query
                    pass
            elif resend_data.organization_website:
                # Find all learners for organization
                learners = self.db.query_learners_for_org(resend_data.organization_website)
            
            if not learners:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'LEARNERS_NOT_FOUND',
                        'message': 'No learners found matching criteria'
                    }
                }
            
            # Trigger certificate regeneration for each learner
            resend_count = 0
            for learner in learners:
                if learner.completion_at and learner.certificate_send_status in ['sent', 'failed']:
                    # Update status to trigger resend
                    self.db.update_learner(learner.id, {
                        'certificate_send_status': 'pending',
                        'last_resend_attempt': datetime.utcnow().isoformat() + 'Z'
                    })
                    resend_count += 1
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': f'Certificate resend triggered for {resend_count} learners'
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
