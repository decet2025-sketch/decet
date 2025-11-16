"""
Appwrite database service with typed helpers.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.storage import Storage
from appwrite.query import Query

from ..models import (
    CourseModel,
    OrganizationModel,
    LearnerModel,
    WebhookEventModel,
    EmailLogModel,
    CertificateSendStatus,
    WebhookStatus,
    EmailStatus,
)

logger = logging.getLogger(__name__)


class AppwriteClient:
    """Appwrite client wrapper with convenient typed helpers."""

    def __init__(self, endpoint: str, project_id: str, api_key: str):
        """Initialize Appwrite client."""
        self.client = Client()
        self.client.set_endpoint(endpoint)
        self.client.set_project(project_id)
        self.client.set_key(api_key)
        
        self.databases = Databases(self.client)
        self.storage = Storage(self.client)
        
        self.project_id = project_id

    def _convert_document_to_model(self, doc: Dict[str, Any], model_class) -> Any:
        """Convert Appwrite document to Pydantic model."""
        # Convert Appwrite $id to id
        if '$id' in doc:
            doc['id'] = doc['$id']
        
        # Convert datetime strings to datetime objects
        for key, value in doc.items():
            if isinstance(value, str) and (key.endswith('_at') or key.endswith('_date')):
                try:
                    doc[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    pass
        
        return model_class(**doc)

    # Course operations
    def get_course_by_course_id(self, course_id: str) -> Optional[CourseModel]:
        """Get course by course_id."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='courses',
                queries=[Query.equal('course_id', course_id)]
            )
            
            if result['documents']:
                return self._convert_document_to_model(result['documents'][0], CourseModel)
            return None
        except Exception as e:
            logger.error(f"Error getting course {course_id}: {e}")
            return None

    def create_course(self, course_data: Dict[str, Any]) -> Optional[CourseModel]:
        """Create a new course."""
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            course_data.update({
                'created_at': now,
                'updated_at': now
            })
            
            result = self.databases.create_document(
                database_id='main',
                collection_id='courses',
                document_id='unique()',
                data=course_data
            )
            
            return self._convert_document_to_model(result, CourseModel)
        except Exception as e:
            logger.error(f"Error creating course: {str(e)}")
            return None

    def update_course(self, course_id: str, update_data: Dict[str, Any]) -> Optional[CourseModel]:
        """Update course by course_id."""
        try:
            # First get the document ID
            course = self.get_course_by_course_id(course_id)
            if not course:
                return None
            
            update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            result = self.databases.update_document(
                database_id='main',
                collection_id='courses',
                document_id=course.id,
                data=update_data
            )
            
            return self._convert_document_to_model(result, CourseModel)
        except Exception as e:
            logger.error(f"Error updating course {course_id}: {e}")
            return None

    def delete_course(self, course_id: str) -> bool:
        """Delete course by course_id."""
        try:
            course = self.get_course_by_course_id(course_id)
            if not course:
                return False
            
            self.databases.delete_document(
                database_id='main',
                collection_id='courses',
                document_id=course.id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting course {course_id}: {e}")
            return False

    def list_courses(self, limit: int = 50, offset: int = 0, search: str = None) -> tuple[List[CourseModel], int]:
        """List courses with pagination and search."""
        try:
            # Build filter queries for both count and data queries
            filter_queries = []
            if search:
                # Search in course name using contains (case-insensitive)
                filter_queries.append(Query.contains('name', search))
            
            # Get total count (without limit/offset)
            count_result = self.databases.list_documents(
                database_id='main',
                collection_id='courses',
                queries=filter_queries
            )
            total_count = count_result['total']
            
            # Get paginated data
            data_queries = filter_queries + [
                Query.limit(limit),
                Query.offset(offset),
                Query.order_desc('$updatedAt')
            ]
            
            result = self.databases.list_documents(
                database_id='main',
                collection_id='courses',
                queries=data_queries
            )
            
            return [
                self._convert_document_to_model(doc, CourseModel)
                for doc in result['documents']
            ], total_count
        except Exception as e:
            logger.error(f"Error listing courses: {e}")
            return [], 0

    # Organization operations
    def list_organizations(self, limit: int = 100, offset: int = 0, search: str = None) -> tuple[List[OrganizationModel], int]:
        """List all organizations with pagination and search."""
        try:
            # Build filter queries for both count and data queries
            filter_queries = []
            if search:
                # Search in organization name using contains (case-insensitive)
                filter_queries.append(Query.contains('name', search))
            
            # Get total count (without limit/offset)
            count_result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=filter_queries
            )
            total_count = count_result['total']
            
            # Get paginated data
            data_queries = filter_queries + [
                Query.limit(limit),
                Query.offset(offset),
                Query.order_desc('$updatedAt')
            ]
            
            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=data_queries
            )
            
            return [
                self._convert_document_to_model(doc, OrganizationModel)
                for doc in result['documents']
            ], total_count
        except Exception as e:
            logger.error(f"Error listing organizations: {e}")
            return [], 0

    def get_organization_by_website(self, website: str) -> Optional[OrganizationModel]:
        """Get organization by website."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=[Query.equal('website', website)]
            )
            
            if result['documents']:
                return self._convert_document_to_model(result['documents'][0], OrganizationModel)
            return None
        except Exception as e:
            logger.error(f"Error getting organization {website}: {e}")
            return None

    def get_organizations_by_websites(self, websites: list[str]) -> list[OrganizationModel]:
        """Get multiple organizations by list of websites."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=[Query.equal('website', websites)]
            )

            return [
                self._convert_document_to_model(doc, OrganizationModel)
                for doc in result.get('documents', [])
            ]
        except Exception as e:
            logger.error(f"Error fetching organizations for websites {websites}: {e}")
            return []


    def get_all_organization_by_website(self, website: str) -> List[OrganizationModel]:
        """Get organization by website."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=[Query.equal('website', website)]
            )

            organizations = []
            if result['documents']:
                for doc in result['documents']:
                    org = self._convert_document_to_model(doc, OrganizationModel)
                    if org:
                        organizations.append(org)
            return organizations
        except Exception as e:
            logger.error(f"Error getting organization {website}: {e}")
            return None

    def get_organizations_by_website_and_sop_email(self, website: str, sop_email: str) -> List[OrganizationModel]:
        """Get organizations by website and sop_email."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=[Query.equal('website', website),
                         Query.equal('sop_email', sop_email)]
            )

            organizations = []
            if result['documents']:
                for doc in result['documents']:
                    org = self._convert_document_to_model(doc, OrganizationModel)
                    if org:
                        organizations.append(org)
            return organizations
        except Exception as e:
            logger.error(f"Error getting organizations for {website} and {sop_email}: {e}")
            return []

    def get_organization_by_id(self, organization_id: str) -> Optional[OrganizationModel]:
        """Get organization by ID."""
        try:
            result = self.databases.get_document(
                database_id='main',
                collection_id='organizations',
                document_id=organization_id
            )
            
            return self._convert_document_to_model(result, OrganizationModel)
        except Exception as e:
            logger.error(f"Error getting organization by ID {organization_id}: {e}")
            return None

    def create_organization(self, org_data: Dict[str, Any]) -> Optional[OrganizationModel]:
        """Create a new organization."""
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            org_data.update({
                'created_at': now,
                'updated_at': now
            })
            
            result = self.databases.create_document(
                database_id='main',
                collection_id='organizations',
                document_id='unique()',
                data=org_data
            )
            
            return self._convert_document_to_model(result, OrganizationModel)
        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            return None

    def update_organization(self, website: str, update_data: Dict[str, Any]) -> Optional[OrganizationModel]:
        """Update organization by website."""
        try:
            org = self.get_organization_by_website(website)
            if not org:
                return None
            
            update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            result = self.databases.update_document(
                database_id='main',
                collection_id='organizations',
                document_id=org.id,
                data=update_data
            )
            
            return self._convert_document_to_model(result, OrganizationModel)
        except Exception as e:
            logger.error(f"Error updating organization {website}: {e}")
            return None

    def update_organization_by_id(self, organization_id: str, update_data: Dict[str, Any]) -> Optional[OrganizationModel]:
        """Update organization by ID."""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            result = self.databases.update_document(
                database_id='main',
                collection_id='organizations',
                document_id=organization_id,
                data=update_data
            )
            
            return self._convert_document_to_model(result, OrganizationModel)
        except Exception as e:
            logger.error(f"Error updating organization by ID {organization_id}: {e}")
            return None

    def update_organizations_password_by_sop_email(
        self,
        sop_email: str,
        new_password: str,
        organization_website: Optional[str] = None
    ) -> int:
        """Update password field for organizations matching the SOP email (and optional website)."""
        try:
            queries = [Query.equal('sop_email', sop_email)]
            if organization_website:
                queries.append(Query.equal('website', organization_website))

            result = self.databases.list_documents(
                database_id='main',
                collection_id='organizations',
                queries=queries
            )

            updated_count = 0
            timestamp = datetime.utcnow().isoformat() + 'Z'

            for document in result.get('documents', []):
                try:
                    self.databases.update_document(
                        database_id='main',
                        collection_id='organizations',
                        document_id=document['$id'],
                        data={
                            'password': new_password,
                            'updated_at': timestamp
                        }
                    )
                    updated_count += 1
                except Exception as update_error:
                    logger.error(
                        f"Failed to update organization password for {sop_email} (document {document.get('$id')}): {update_error}"
                    )

            return updated_count
        except Exception as e:
            logger.error(f"Error updating organization password for {sop_email}: {e}")
            return 0

    def delete_organization(self, website: str) -> bool:
        """Delete organization by website."""
        try:
            org = self.get_organization_by_website(website)
            if not org:
                return False
            
            self.databases.delete_document(
                database_id='main',
                collection_id='organizations',
                document_id=org.id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting organization {website}: {e}")
            return False

    # Learner operations
    def get_learner_by_course_and_email(self, course_id: str, email: str) -> Optional[LearnerModel]:
        """Get learner by course_id and email."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=[
                    Query.equal('course_id', course_id),
                    Query.equal('email', email)
                ]
            )
            
            if result['documents']:
                return self._convert_document_to_model(result['documents'][0], LearnerModel)
            return None
        except Exception as e:
            logger.error(f"Error getting learner {course_id}/{email}: {e}")
            return None

    def create_learner_if_not_exists(self, learner_data: Dict[str, Any]) -> Optional[LearnerModel]:
        """Create learner if not exists (idempotent)."""
        try:
            # Check if learner already exists
            existing = self.get_learner_by_course_and_email(
                learner_data['course_id'],
                learner_data['email']
            )
            if existing:
                return existing
            
            # Set default status and timestamps
            now = datetime.utcnow().isoformat() + 'Z'
            learner_data['enrollment_status'] = 'pending'
            learner_data['certificate_send_status'] = CertificateSendStatus.PENDING.value
            learner_data['created_at'] = now
            learner_data['updated_at'] = now
            
            result = self.databases.create_document(
                database_id='main',
                collection_id='learners',
                document_id='unique()',
                data=learner_data
            )
            
            return self._convert_document_to_model(result, LearnerModel)
        except Exception as e:
            logger.error(f"Error creating learner: {e}")
            return None

    def update_learner(self, learner_id: str, update_data: Dict[str, Any]) -> Optional[LearnerModel]:
        """Update learner by ID."""
        try:
            result = self.databases.update_document(
                database_id='main',
                collection_id='learners',
                document_id=learner_id,
                data=update_data
            )
            
            return self._convert_document_to_model(result, LearnerModel)
        except Exception as e:
            logger.error(f"Error updating learner {learner_id}: {e}")
            return None

    def delete_learner(self, learner_id: str) -> bool:
        """Delete learner by ID."""
        try:
            self.databases.delete_document(
                database_id='main',
                collection_id='learners',
                document_id=learner_id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting learner {learner_id}: {e}")
            return False

    def update_learners_organization_website(self, old_website: str, new_website: str) -> int:
        """Update all learners' organization_website from old to new."""
        try:
            # Get all learners with the old website
            learners = self.query_learners_for_org(old_website, limit=10000, offset=0)
            
            updated_count = 0
            for learner in learners:
                try:
                    self.databases.update_document(
                        database_id='main',
                        collection_id='learners',
                        document_id=learner.id,
                        data={'organization_website': new_website}
                    )
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating learner {learner.id}: {e}")
                    continue
            
            logger.info(f"Updated {updated_count} learners from {old_website} to {new_website}")
            return updated_count
        except Exception as e:
            logger.error(f"Error updating learners organization website: {e}")
            return 0

    def update_sop_user_organization_website(self, old_website: str, new_website: str) -> int:
        """Update SOP user's organization_website preference in Appwrite Users collection."""
        try:
            from appwrite.services.users import Users
            
            users = Users(self.client)
            
            # Get organization to find the SOP email
            organization = self.get_organization_by_website(new_website)
            if not organization:
                logger.error(f"Organization with website {new_website} not found")
                return 0
            
            sop_email = organization.sop_email
            
            # Find the SOP user by email
            user_list = users.list(search=sop_email)
            
            if not user_list['users']:
                logger.warning(f"SOP user with email {sop_email} not found")
                return 0
            
            user = user_list['users'][0]
            user_prefs = user.get('prefs', {})
            current_org_website = user_prefs.get('organization_website')
            
            # Only update if the current preference matches the old website
            if current_org_website == old_website:
                # Update user preferences
                updated_prefs = user_prefs.copy()
                updated_prefs['organization_website'] = new_website
                
                users.update_prefs(
                    user_id=user['$id'],
                    prefs=updated_prefs
                )
                
                logger.info(f"Updated SOP user {sop_email} organization_website from {old_website} to {new_website}")
                return 1
            else:
                logger.info(f"SOP user {sop_email} already has correct organization_website: {current_org_website}")
                return 0
                
        except Exception as e:
            logger.error(f"Error updating SOP user organization website: {e}")
            return 0

    def mark_learner_completed(self, course_id: str, email: str) -> Optional[LearnerModel]:
        """Mark learner as completed."""
        try:
            learner = self.get_learner_by_course_and_email(course_id, email)
            if not learner:
                return None
            
            update_data = {
                'completion_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            return self.update_learner(learner.id, update_data)
        except Exception as e:
            logger.error(f"Error marking learner completed {course_id}/{email}: {e}")
            return None

    def query_learners_for_org(self, organization_website: str, limit: int = 50, offset: int = 0, search: str = None) -> List[LearnerModel]:
        """Query learners for organization with search."""
        try:
            queries = [
                Query.equal('organization_website', organization_website),
                Query.limit(1000),  # Get more to account for client-side filtering
                Query.offset(0),    # Reset offset for client-side filtering
                Query.order_desc('$updatedAt')
            ]
            
            # Get all learners for organization first (no search filter at database level)
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=queries
            )
            
            learners = [
                self._convert_document_to_model(doc, LearnerModel)
                for doc in result['documents']
            ]
            
            # Apply wildcard search filter in Python if provided (search across name, email, and organization_website)
            if search:
                search_term = search.lower()
                learners = [
                    learner for learner in learners
                    if (search_term in learner.name.lower() or 
                        search_term in learner.email.lower() or 
                        search_term in learner.organization_website.lower())
                ]
            
            # Apply pagination after filtering
            start_idx = offset
            end_idx = offset + limit
            return learners[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error querying learners for org {organization_website}: {e}")
            return []

    def query_learners_for_course(self, course_id: str, limit: int = 50, offset: int = 0, search: str = None) -> List[LearnerModel]:
        """Query learners for course with search."""
        try:
            queries = [
                Query.equal('course_id', course_id),
                Query.limit(1000),  # Get more to account for client-side filtering
                Query.offset(0),    # Reset offset for client-side filtering
                Query.order_desc('$updatedAt')
            ]
            
            # Get all learners for course first (no search filter at database level)
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=queries
            )
            
            learners = [
                self._convert_document_to_model(doc, LearnerModel)
                for doc in result['documents']
            ]
            
            # Apply wildcard search filter in Python if provided (search across name, email, and organization_website)
            if search:
                search_term = search.lower()
                learners = [
                    learner for learner in learners
                    if (search_term in learner.name.lower() or 
                        search_term in learner.email.lower() or 
                        search_term in learner.organization_website.lower())
                ]
            
            # Apply pagination after filtering
            start_idx = offset
            end_idx = offset + limit
            return learners[start_idx:end_idx]
        except Exception as e:
            logger.error(f"Error querying learners for course {course_id}: {e}")
            return []

    def query_all_learners(self, limit: int = 50, offset: int = 0, search: str = None) -> List[LearnerModel]:
        """Query all learners with search."""
        try:
            queries = [
                Query.limit(limit),
                Query.offset(offset),
                Query.order_desc('$updatedAt')
            ]
            
            # Add search functionality
            if search:
                # Search in learner name using contains (case-insensitive)
                queries.append(Query.contains('name', search))
            
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=queries
            )
            
            return [
                self._convert_document_to_model(doc, LearnerModel)
                for doc in result['documents']
            ]
        except Exception as e:
            logger.error(f"Error querying all learners: {e}")
            return []

    # Webhook operations
    def create_webhook_event(self, event_data: Dict[str, Any]) -> Optional[WebhookEventModel]:
        """Create webhook event."""
        try:
            # Ensure status is set if not provided
            if 'status' not in event_data:
                event_data['status'] = WebhookStatus.RECEIVED.value
            
            result = self.databases.create_document(
                database_id='main',
                collection_id='webhook_events',
                document_id='unique()',
                data=event_data
            )
            
            return self._convert_document_to_model(result, WebhookEventModel)
        except Exception as e:
            logger.error(f"Error creating webhook event: {e}")
            return None

    def get_webhook_event(self, event_id: str) -> Optional[WebhookEventModel]:
        """Get webhook event by ID."""
        try:
            result = self.databases.get_document(
                database_id='main',
                collection_id='webhook_events',
                document_id=event_id
            )
            
            return self._convert_document_to_model(result, WebhookEventModel)
        except Exception as e:
            logger.error(f"Error getting webhook event {event_id}: {e}")
            return None

    def update_webhook_event(self, event_id: str, update_data: Dict[str, Any]) -> Optional[WebhookEventModel]:
        """Update webhook event."""
        try:
            result = self.databases.update_document(
                database_id='main',
                collection_id='webhook_events',
                document_id=event_id,
                data=update_data
            )
            
            return self._convert_document_to_model(result, WebhookEventModel)
        except Exception as e:
            logger.error(f"Error updating webhook event {event_id}: {e}")
            return None

    def list_webhook_events(self, limit: int = 50, offset: int = 0, status: Optional[WebhookStatus] = None) -> List[WebhookEventModel]:
        """List webhook events."""
        try:
            queries = [
                Query.limit(limit),
                Query.offset(offset),
                Query.order_desc('$updatedAt')
            ]
            
            if status:
                queries.append(Query.equal('status', status.value))
            
            result = self.databases.list_documents(
                database_id='main',
                collection_id='webhook_events',
                queries=queries
            )
            
            return [
                self._convert_document_to_model(doc, WebhookEventModel)
                for doc in result['documents']
            ]
        except Exception as e:
            logger.error(f"Error listing webhook events: {e}")
            return []

    # Email log operations
    def create_email_log(self, log_data: Dict[str, Any]) -> Optional[EmailLogModel]:
        """Create email log."""
        try:
            # Don't add extra fields - use only what's provided
            # The email_logs table has specific required fields
            
            result = self.databases.create_document(
                database_id='main',
                collection_id='email_logs',
                document_id='unique()',
                data=log_data
            )
            
            return self._convert_document_to_model(result, EmailLogModel)
        except Exception as e:
            logger.error(f"Error creating email log: {e}")
            return None

    # Storage operations
    def save_certificate_file(self, file_content: bytes, filename: str, bucket_id: str) -> Optional[str]:
        """Save certificate file to storage."""
        try:
            result = self.storage.create_file(
                bucket_id=bucket_id,
                file_id='unique()',
                file=file_content,
                on_progress=None
            )
            
            return result['$id']
        except Exception as e:
            logger.error(f"Error saving certificate file {filename}: {e}")
            return None

    def get_file_content(self, file_id: str, bucket_id: str) -> Optional[bytes]:
        """Get file content from storage."""
        try:
            result = self.storage.get_file(
                bucket_id=bucket_id,
                file_id=file_id
            )
            
            return result
        except Exception as e:
            logger.error(f"Error getting file content {file_id}: {e}")
            return None

    def get_file_download_url(self, file_id: str, bucket_id: str) -> Optional[str]:
        """Get file download URL."""
        try:
            import os
            
            # Get endpoint and project ID from environment variables
            endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
            project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')
            
            # Remove /v1 from endpoint if present
            if endpoint.endswith('/v1'):
                endpoint = endpoint[:-3]
            
            download_url = f"{endpoint}/v1/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
            
            return download_url
        except Exception as e:
            logger.error(f"Error getting file download URL {file_id}: {e}")
            return None

    def delete_file(self, file_id: str, bucket_id: str) -> bool:
        """Delete file from storage."""
        try:
            self.storage.delete_file(
                bucket_id=bucket_id,
                file_id=file_id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False

    def upload_file(self, file_bytes: bytes, filename: str, bucket_id: str, content_type: str = 'application/octet-stream', context=None) -> Optional[Dict[str, Any]]:
        """Upload file to Appwrite storage."""
        try:
            import tempfile
            import os
            
            # Use context logging if available, otherwise use logger
            def log_msg(msg):
                if context:
                    context.log(msg)
                else:
                    logger.info(msg)
            
            def log_error(msg):
                if context:
                    context.error(msg)
                else:
                    logger.error(msg)
            
            log_msg(f"Starting file upload process for: {filename}")
            log_msg(f"File size: {len(file_bytes)} bytes")
            log_msg(f"Target bucket: {bucket_id}")
            log_msg(f"Content type: {content_type}")
            
            # Create a temporary file
            log_msg("Creating temporary file...")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name
                log_msg(f"Temporary file created at: {temp_file_path}")
            
            try:
                # Upload file to storage using InputFile
                log_msg("Opening file for upload...")
                from appwrite.input_file import InputFile
                
                log_msg("Calling Appwrite storage.create_file...")
                log_msg(f"Parameters: bucket_id={bucket_id}, file_id='unique()', file=InputFile.from_path(temp_file_path), permissions=['read(\"any\")']")
                
                result = self.storage.create_file(
                    bucket_id=bucket_id,
                    file_id='unique()',
                    file=InputFile.from_path(temp_file_path),
                    permissions=['read("any")']  # Allow public read access
                )
                
                log_msg(f"Appwrite storage.create_file completed successfully")
                log_msg(f"Result type: {type(result)}")
                log_msg(f"Result content: {result}")
                
                if result and isinstance(result, dict):
                    file_id = result.get('$id')
                    log_msg(f"File uploaded successfully: {filename} -> {file_id}")
                    return result
                else:
                    log_msg(f"Unexpected result format: {result}")
                    return None
                
            finally:
                # Clean up temporary file
                log_msg("Cleaning up temporary file...")
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    log_msg("Temporary file deleted successfully")
                else:
                    log_msg("Temporary file not found for cleanup")
            
        except Exception as e:
            log_error(f"Error uploading file {filename}: {e}")
            import traceback
            log_error(f"Full traceback: {traceback.format_exc()}")
            return None

    def get_learners_count_for_org(self, organization_website: str, search: str = None) -> int:
        """Get total count of learners for organization with optional search."""
        try:
            queries = [
                Query.equal('organization_website', organization_website)
            ]
            
            # Add search functionality
            if search:
                # Search in learner name using contains (case-insensitive)
                queries.append(Query.contains('name', search))
            
            # Get count without limit/offset for accurate total
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=queries
            )
            
            return len(result['documents'])
        except Exception as e:
            logger.error(f"Error getting learners count for org {organization_website}: {e}")
            return 0
