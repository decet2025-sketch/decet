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
            if isinstance(value, str) and key.endswith('_at'):
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

    def list_courses(self, limit: int = 50, offset: int = 0) -> List[CourseModel]:
        """List courses with pagination."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='courses',
                queries=[
                    Query.limit(limit),
                    Query.offset(offset),
                    Query.order_desc('created_at')
                ]
            )
            
            return [
                self._convert_document_to_model(doc, CourseModel)
                for doc in result['documents']
            ]
        except Exception as e:
            logger.error(f"Error listing courses: {e}")
            return []

    # Organization operations
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

    def query_learners_for_org(self, organization_website: str, limit: int = 50, offset: int = 0) -> List[LearnerModel]:
        """Query learners for organization."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=[
                    Query.equal('organization_website', organization_website),
                    Query.limit(limit),
                    Query.offset(offset),
                    Query.order_desc('created_at')
                ]
            )
            
            return [
                self._convert_document_to_model(doc, LearnerModel)
                for doc in result['documents']
            ]
        except Exception as e:
            logger.error(f"Error querying learners for org {organization_website}: {e}")
            return []

    def query_learners_for_course(self, course_id: str, limit: int = 50, offset: int = 0) -> List[LearnerModel]:
        """Query learners for course."""
        try:
            result = self.databases.list_documents(
                database_id='main',
                collection_id='learners',
                queries=[
                    Query.equal('course_id', course_id),
                    Query.limit(limit),
                    Query.offset(offset),
                    Query.order_desc('created_at')
                ]
            )
            
            return [
                self._convert_document_to_model(doc, LearnerModel)
                for doc in result['documents']
            ]
        except Exception as e:
            logger.error(f"Error querying learners for course {course_id}: {e}")
            return []

    # Webhook operations
    def create_webhook_event(self, event_data: Dict[str, Any]) -> Optional[WebhookEventModel]:
        """Create webhook event."""
        try:
            event_data.update({
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'status': WebhookStatus.RECEIVED.value,
                'attempts': 0
            })
            
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
                Query.order_desc('received_at')
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
            log_data.update({
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'retry_count': 0
            })
            
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
            result = self.storage.get_file_download(
                bucket_id=bucket_id,
                file_id=file_id
            )
            
            return result
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
