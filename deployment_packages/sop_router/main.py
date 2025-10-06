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
    ListOrgLearnersPayload, DownloadCertificatePayload, ResendCertificatePayload,
    ListActivityLogsPayload, ActivityType, ActivityStatus, SOPLearnerStatisticsPayload
)
from shared.services.db import AppwriteClient
from shared.services.email_service_simple import EmailService
from shared.services.auth import AuthService
from shared.services.activity_log import ActivityLogService
import requests

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
        
        # Initialize activity log service
        self.activity_log = ActivityLogService(
            client=self.db.client,
            database_id='main'
        )
        
        # Certificate worker configuration
        self.certificate_worker_url = f"{endpoint}/functions/certificate_worker/executions"
        self.certificate_worker_headers = {
            'Content-Type': 'application/json',
            'X-Appwrite-Project': project_id,
            'X-Appwrite-Key': api_key
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
                SOPActionType.LIST_ACTIVITY_LOGS: self._handle_list_activity_logs,
                SOPActionType.LEARNER_STATISTICS: self._handle_learner_statistics,
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
        """Handle LIST_ORG_LEARNERS action with grouped response."""
        try:
            # Validate payload
            list_data = ListOrgLearnersPayload(**payload)
            
            # Check if SOP can access this organization
            if not self.auth.can_access_organization(auth_context, list_data.organization_website):
                return self.auth.create_organization_access_denied_response()
            
            # Get all learners for organization (we'll group them by email)
            # Don't apply offset here - we need all learners to group properly
            all_learners = self.db.query_learners_for_org(
                list_data.organization_website,
                1000,  # Get a large number to ensure we get all learners
                0,     # No offset - we'll apply pagination after grouping
                list_data.search
            )
            
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
                    completion_percentage = 100.0

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
            
            # Get organization info
            org = self.db.get_organization_by_website(list_data.organization_website)
            organization_info = {
                'name': org.name if org else 'Unknown Organization',
                'website': list_data.organization_website,
                'sop_email': org.sop_email if org else None,
                'created_at': org.created_at.isoformat() if org and org.created_at else None
            }
            
            # Populate organization info and format response
            grouped_learners = []
            for email, group in learner_groups.items():
                group['organization_info'] = organization_info
                
                # Sort courses by creation date (handle None values)
                group['courses'].sort(key=lambda x: x['created_at'] or '1900-01-01T00:00:00', reverse=True)
                grouped_learners.append(group)
            
            # Sort learners by name
            grouped_learners.sort(key=lambda x: x['learner_info']['name'])
            
            # Apply pagination to grouped results
            total_learners = len(grouped_learners)
            start_idx = list_data.offset
            end_idx = start_idx + list_data.limit
            paginated_learners = grouped_learners[start_idx:end_idx]
            
            # Calculate summary statistics
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
                str(download_data.learner_email)
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
                    str(resend_data.learner_email)
                )
            # elif resend_data.organization_website:
            #     # Find learners for organization
            #     learners = self.db.query_learners_for_org(resend_data.organization_website)
            #     if learners:
            #         # For SOP resend, we'll resend for all completed learners
            #         learners_to_resend = [
            #             l for l in learners
            #             if l.completion_date and l.certificate_send_status in ['sent', 'failed']
            #         ]
            #     else:
            #         learners_to_resend = []
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
                if not learner.completion_date:
                    return {
                        'ok': False,
                        'status': 400,
                        'error': {
                            'code': 'LEARNER_NOT_COMPLETED',
                            'message': 'Learner has not completed the course yet'
                        }
                    }

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

    def _handle_list_activity_logs(self, payload: Dict[str, Any], auth_context) -> Dict[str, Any]:
        """Handle LIST_ACTIVITY_LOGS action (SOP view - organization filtered)."""
        try:
            # Validate payload
            list_data = ListActivityLogsPayload(**payload)
            
            # SOP users can only see logs for their organization
            organization_website = getattr(auth_context, 'organization_website', None)
            if not organization_website:
                return {
                    'ok': False,
                    'status': 403,
                    'error': {
                        'code': 'ACCESS_DENIED',
                        'message': 'SOP user must have organization_website in token'
                    }
                }
            
            # Override organization_website to ensure SOP only sees their org logs
            list_data.organization_website = organization_website
            
            # Get activity logs for organization only
            logs, total_count = self.activity_log.get_activity_logs_for_organization(
                organization_website=organization_website,
                limit=list_data.limit,
                offset=list_data.offset,
                activity_type=list_data.activity_type,
                status=list_data.status
            )
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'logs': [json.loads(log.json()) for log in logs],
                    'organization_website': organization_website
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
        """Handle LEARNER_STATISTICS action for SOP users (organization-specific)."""
        try:
            # Validate payload
            stats_data = SOPLearnerStatisticsPayload(**payload)
            
            # SOP users can only see statistics for their organization
            organization_website = getattr(auth_context, 'organization_website', None)
            if not organization_website:
                return {
                    'ok': False,
                    'status': 403,
                    'error': {
                        'code': 'ACCESS_DENIED',
                        'message': 'SOP user must have organization_website in token'
                    }
                }
            
            # Get all learners for this organization
            all_learners = self.db.query_learners_for_org(organization_website, limit=10000, offset=0)
            
            # Calculate metrics
            total_learners = len(set(learner.email for learner in all_learners))  # Unique learners
            
            # Active learners (currently enrolled or in progress)
            active_learners = len(set(
                learner.email for learner in all_learners 
                if getattr(learner, 'enrollment_status', 'pending') in ['enrolled', 'in_progress']
            ))
            
            # Active enrollments (total course enrollments that are active)
            active_enrollments = len([
                learner for learner in all_learners 
                if getattr(learner, 'enrollment_status', 'pending') in ['enrolled', 'in_progress']
            ])
            
            # Completed courses (total completed enrollments)
            completed_courses = len([
                learner for learner in all_learners 
                if getattr(learner, 'enrollment_status', 'pending') == 'completed'
            ])
            
            # Certificates generated (learners with certificate_file_id)
            certificates_generated = len([
                learner for learner in all_learners 
                if getattr(learner, 'certificate_file_id', None) is not None
            ])
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'total_learners': total_learners,
                    'active_learners': active_learners,
                    'active_enrollments': active_enrollments,
                    'completed_courses': completed_courses,
                    'certificates_generated': certificates_generated,
                    'organization_website': organization_website
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting SOP learner statistics: {e}")
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
