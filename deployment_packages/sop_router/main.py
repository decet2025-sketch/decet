"""
SOP Router - Handles operations for Single Point of Contact users.
"""

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
    ActionRequest, SOPActionType, BaseResponse,
    ListOrgLearnersPayload, DownloadCertificatePayload, ResendCertificatePayload
)
from shared.services.db import AppwriteClient
from shared.services.email_service_simple import EmailService
from shared.services.auth import AuthService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SOPRouter:
    """SOP router for organization-specific operations."""

    def __init__(self):
        """Initialize SOP router with services."""
        # Initialize Appwrite client
        endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')  # Fallback to project ID
        api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')

        logger.info(f"Database client config - endpoint: {endpoint}, project: {project_id}, api_key: {api_key[:20] if api_key else 'None'}...")


        # Initialize Appwrite client
        self.db = AppwriteClient(
            endpoint=endpoint,
            project_id=project_id,
            api_key=api_key
        )
        
        # Initialize email service
        self.email = EmailService(self.db.client)
        
        # Initialize auth service
        self.auth = AuthService()

    def handle_request(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle incoming SOP request."""
        try:
            # Validate authentication
            auth_context = self.auth.validate_request_auth(headers)
            if not auth_context or not self.auth.require_sop(auth_context):
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
                SOPActionType.LIST_ORG_LEARNERS: self._handle_list_org_learners,
                SOPActionType.DOWNLOAD_CERTIFICATE: self._handle_download_certificate,
                SOPActionType.RESEND_CERTIFICATE: self._handle_resend_certificate,
            }
            
            handler = handler_map.get(action_request.action)
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
            logger.error(f"Error handling SOP request: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Internal server error'
                }
            }

    def _handle_list_org_learners(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_ORG_LEARNERS action."""
        try:
            # Validate payload
            list_data = ListOrgLearnersPayload(**payload)
            
            # Check if SOP can access this organization
            if not self.auth.can_access_organization(auth_context, list_data.organization_website):
                return self.auth.create_organization_access_denied_response()
            
            # Get learners for organization
            learners = self.db.query_learners_for_org(
                list_data.organization_website,
                list_data.limit,
                list_data.offset
            )
            
            # Filter out sensitive information for SOP view
            filtered_learners = []
            for learner in learners:
                learner_dict = learner.dict()
                # Remove internal fields that SOP shouldn't see
                learner_dict.pop('enrollment_error', None)
                filtered_learners.append(learner_dict)
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'learners': filtered_learners,
                    'organization_website': list_data.organization_website
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing org learners: {e}")
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
            
            # Check if SOP can access this learner's organization
            if not self.auth.can_access_organization(auth_context, learner.organization_website):
                return self.auth.create_organization_access_denied_response()
            
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
            
            # Get certificate file
            certificate_bucket_id = os.getenv('CERTIFICATE_BUCKET_ID', 'certificates')
            certificate_content = self.db.get_file_content(
                learner.certificate_file_id,
                certificate_bucket_id
            )
            
            if not certificate_content:
                return {
                    'ok': False,
                    'status': 404,
                    'error': {
                        'code': 'CERTIFICATE_FILE_NOT_FOUND',
                        'message': 'Certificate file not found in storage'
                    }
                }
            
            # Generate download URL (signed URL for security)
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
                    'generated_at': learner.certificate_generated_at
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
                    resend_data.learner_email
                )
            elif resend_data.organization_website:
                # Find learners for organization
                learners = self.db.query_learners_for_org(resend_data.organization_website)
                if learners:
                    # For SOP resend, we'll resend for all completed learners
                    learners_to_resend = [
                        l for l in learners 
                        if l.completion_at and l.certificate_send_status in ['sent', 'failed']
                    ]
                else:
                    learners_to_resend = []
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
                # Check if SOP can access this learner's organization
                if not self.auth.can_access_organization(auth_context, learner.organization_website):
                    return self.auth.create_organization_access_denied_response()
                
                # Check if learner has completed the course
                if not learner.completion_at:
                    return {
                        'ok': False,
                        'status': 400,
                        'error': {
                            'code': 'LEARNER_NOT_COMPLETED',
                            'message': 'Learner has not completed the course yet'
                        }
                    }
                
                # Update status to trigger resend
                self.db.update_learner(learner.id, {
                    'certificate_send_status': 'pending',
                    'last_resend_attempt': datetime.utcnow().isoformat() + 'Z'
                })
                
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'message': f'Certificate resend requested for {learner.email}',
                        'learner_email': learner.email,
                        'course_id': resend_data.course_id
                    }
                }
            
            # Handle organization-wide resend
            elif resend_data.organization_website:
                # Check if SOP can access this organization
                if not self.auth.can_access_organization(auth_context, resend_data.organization_website):
                    return self.auth.create_organization_access_denied_response()
                
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
                
                # Update status for all learners
                resend_count = 0
                for learner in learners_to_resend:
                    self.db.update_learner(learner.id, {
                        'certificate_send_status': 'pending',
                        'last_resend_attempt': datetime.utcnow().isoformat() + 'Z'
                    })
                    resend_count += 1
                
                return {
                    'ok': True,
                    'status': 200,
                    'data': {
                        'message': f'Certificate resend requested for {resend_count} learners',
                        'organization_website': resend_data.organization_website,
                        'resend_count': resend_count
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

    def get_organization_stats(self, organization_website: str, auth_context) -> Dict[str, Any]:
        """Get organization statistics for SOP dashboard."""
        try:
            # Check if SOP can access this organization
            if not self.auth.can_access_organization(auth_context, organization_website):
                return self.auth.create_organization_access_denied_response()
            
            # Get all learners for organization
            learners = self.db.query_learners_for_org(organization_website, limit=1000, offset=0)
            
            # Calculate statistics
            total_learners = len(learners)
            completed_learners = len([l for l in learners if l.completion_at])
            certificates_generated = len([l for l in learners if l.certificate_generated_at])
            certificates_sent = len([l for l in learners if l.certificate_send_status == 'sent'])
            certificates_failed = len([l for l in learners if l.certificate_send_status == 'failed'])
            certificates_pending = len([l for l in learners if l.certificate_send_status == 'pending'])
            
            # Group by course
            course_stats = {}
            for learner in learners:
                course_id = learner.course_id
                if course_id not in course_stats:
                    course_stats[course_id] = {
                        'total': 0,
                        'completed': 0,
                        'certificates_sent': 0
                    }
                
                course_stats[course_id]['total'] += 1
                if learner.completion_at:
                    course_stats[course_id]['completed'] += 1
                if learner.certificate_send_status == 'sent':
                    course_stats[course_id]['certificates_sent'] += 1
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'organization_website': organization_website,
                    'total_learners': total_learners,
                    'completed_learners': completed_learners,
                    'certificates_generated': certificates_generated,
                    'certificates_sent': certificates_sent,
                    'certificates_failed': certificates_failed,
                    'certificates_pending': certificates_pending,
                    'completion_rate': (completed_learners / total_learners * 100) if total_learners > 0 else 0,
                    'certificate_send_rate': (certificates_sent / completed_learners * 100) if completed_learners > 0 else 0,
                    'course_stats': course_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting organization stats: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'STATS_ERROR',
                    'message': f'Failed to get organization stats: {str(e)}'
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
                # First parse the outer JSON
                outer_data = json.loads(data)
                
                # Check if there's a 'body' field containing the actual data
                if 'body' in outer_data:
                    # Parse the inner JSON from the body field
                    request_data = json.loads(outer_data['body'])
                else:
                    # Use the outer data directly
                    request_data = outer_data
                    
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
        
        # Get headers
        headers = {}
        if hasattr(context.req, 'headers'):
            headers = dict(context.req.headers)
        
        # Check if JWT token is in the request data
        jwt_token = request_data.get('jwt_token')
        if jwt_token:
            # Add JWT to headers for authentication
            headers['Authorization'] = f'Bearer {jwt_token}'
        
        # Check for stats action
        if request_data.get('action') == 'get_organization_stats':
            router = SOPRouter()
            auth_context = router.auth.validate_request_auth(headers)
            if not auth_context or not router.auth.require_sop(auth_context):
                return context.res.json(router.auth.create_unauthorized_response())
            
            org_website = request_data.get('organization_website')
            if not org_website:
                return context.res.json({
                    "ok": False,
                    "error": "MISSING_ORGANIZATION",
                    "message": "organization_website is required for stats"
                }, 400)
            
            result = router.get_organization_stats(org_website, auth_context)
            return context.res.json(result)
        
        # Initialize router
        router = SOPRouter()
        
        # Handle request
        response = router.handle_request(request_data, headers)
        
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
