"""
Activity Log Service for tracking platform activities.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query

from ..models import ActivityLogModel, ActivityType, ActivityStatus

logger = logging.getLogger(__name__)


class ActivityLogService:
    """Service for managing activity logs."""
    
    def __init__(self, client: Client, database_id: str = 'main'):
        """Initialize ActivityLogService."""
        self.client = client
        self.database_id = database_id
        self.databases = Databases(client)
        self.collection_id = 'activity_logs'
    
    def log_activity(
        self,
        activity_type: ActivityType,
        actor: str,
        details: str,
        status: ActivityStatus = ActivityStatus.SUCCESS,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target: Optional[str] = None,
        target_email: Optional[str] = None,
        organization_website: Optional[str] = None,
        course_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Log an activity.
        
        Args:
            activity_type: Type of activity
            actor: Who performed the action
            details: Description of the activity
            status: Success/Failed status
            actor_email: Email of the actor
            actor_role: Role of the actor (admin/sop)
            target: Target of the action
            target_email: Email of the target
            organization_website: Organization website
            course_id: Course ID if applicable
            error_message: Error message if failed
            metadata: Additional metadata as dict
            timestamp: When the activity occurred (defaults to now)
        
        Returns:
            Document ID if successful, None if failed
        """
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            # Prepare document data
            document_data = {
                'activity_type': activity_type.value,
                'actor': actor,
                'details': details,
                'status': status.value,
                'timestamp': timestamp.isoformat() + 'Z'
            }
            
            # Add optional fields
            if actor_email:
                document_data['actor_email'] = actor_email
            if actor_role:
                document_data['actor_role'] = actor_role
            if target:
                document_data['target'] = target
            if target_email:
                document_data['target_email'] = target_email
            if organization_website:
                document_data['organization_website'] = organization_website
            if course_id:
                document_data['course_id'] = course_id
            if error_message:
                document_data['error_message'] = error_message
            if metadata:
                document_data['metadata'] = json.dumps(metadata)
            
            # Create document
            result = self.databases.create_document(
                database_id=self.database_id,
                collection_id=self.collection_id,
                document_id='unique()',
                data=document_data
            )
            
            logger.info(f"Activity logged: {activity_type.value} by {actor} - {status.value}")
            return result['$id']
            
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
            return None
    
    def get_activity_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        activity_type: Optional[ActivityType] = None,
        status: Optional[ActivityStatus] = None,
        organization_website: Optional[str] = None,
        course_id: Optional[str] = None,
        actor: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> tuple[List[ActivityLogModel], int]:
        """
        Get activity logs with optional filters.
        
        Args:
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            activity_type: Filter by activity type
            status: Filter by status
            organization_website: Filter by organization
            course_id: Filter by course
            actor: Filter by actor
            start_date: Filter logs after this date
            end_date: Filter logs before this date
        
        Returns:
            Tuple of (List of ActivityLogModel objects, total_count)
        """
        try:
            # Build filter queries for both count and data queries
            filter_queries = []
            if activity_type:
                filter_queries.append(Query.equal('activity_type', activity_type.value))
            if status:
                filter_queries.append(Query.equal('status', status.value))
            if organization_website:
                filter_queries.append(Query.equal('organization_website', organization_website))
            if course_id:
                filter_queries.append(Query.equal('course_id', course_id))
            if actor:
                filter_queries.append(Query.equal('actor', actor))
            if start_date:
                filter_queries.append(Query.greater_than_equal('timestamp', start_date.isoformat() + 'Z'))
            if end_date:
                filter_queries.append(Query.less_than_equal('timestamp', end_date.isoformat() + 'Z'))
            
            # Get total count (without limit/offset)
            count_result = self.databases.list_documents(
                database_id=self.database_id,
                collection_id=self.collection_id,
                queries=filter_queries
            )
            total_count = count_result['total']
            
            # Get paginated data
            data_queries = filter_queries + [
                Query.limit(limit),
                Query.offset(offset),
                Query.order_desc('timestamp')
            ]
            
            result = self.databases.list_documents(
                database_id=self.database_id,
                collection_id=self.collection_id,
                queries=data_queries
            )
            
            # Convert to models
            logs = []
            for doc in result['documents']:
                try:
                    log = self._convert_document_to_model(doc)
                    logs.append(log)
                except Exception as e:
                    logger.error(f"Failed to convert document to model: {e}")
                    continue
            
            return logs, total_count
            
        except Exception as e:
            logger.error(f"Failed to get activity logs: {e}")
            return [], 0
    
    def get_activity_logs_for_organization(
        self,
        organization_website: str,
        limit: int = 50,
        offset: int = 0,
        activity_type: Optional[ActivityType] = None,
        status: Optional[ActivityStatus] = None
    ) -> tuple[List[ActivityLogModel], int]:
        """
        Get activity logs for a specific organization.
        
        Args:
            organization_website: Organization website
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            activity_type: Filter by activity type
            status: Filter by status
        
        Returns:
            Tuple of (List of ActivityLogModel objects, total_count)
        """
        return self.get_activity_logs(
            limit=limit,
            offset=offset,
            activity_type=activity_type,
            status=status,
            organization_website=organization_website
        )
    
    def _convert_document_to_model(self, doc: Dict[str, Any]) -> ActivityLogModel:
        """Convert Appwrite document to ActivityLogModel."""
        try:
            # Parse metadata if it exists
            metadata = None
            if doc.get('metadata'):
                try:
                    metadata = json.loads(doc['metadata'])
                except json.JSONDecodeError:
                    metadata = doc['metadata']
            
            return ActivityLogModel(
                id=doc['$id'],
                activity_type=ActivityType(doc['activity_type']),
                actor=doc['actor'],
                actor_email=doc.get('actor_email'),
                actor_role=doc.get('actor_role'),
                target=doc.get('target'),
                target_email=doc.get('target_email'),
                organization_website=doc.get('organization_website'),
                course_id=doc.get('course_id'),
                details=doc['details'],
                status=ActivityStatus(doc['status']),
                error_message=doc.get('error_message'),
                metadata=json.dumps(metadata) if metadata else None,
                timestamp=datetime.fromisoformat(doc['timestamp'].replace('Z', '+00:00'))
            )
        except Exception as e:
            logger.error(f"Failed to convert document to model: {e}")
            raise
    
    def get_activity_stats(
        self,
        organization_website: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get activity statistics.
        
        Args:
            organization_website: Filter by organization
            start_date: Filter logs after this date
            end_date: Filter logs before this date
        
        Returns:
            Dictionary with activity statistics
        """
        try:
            # Get all logs for the period
            logs = self.get_activity_logs(
                limit=1000,  # Get more logs for stats
                activity_type=None,
                status=None,
                organization_website=organization_website,
                start_date=start_date,
                end_date=end_date
            )
            
            # Calculate stats
            total_activities = len(logs)
            successful_activities = len([log for log in logs if log.status == ActivityStatus.SUCCESS])
            failed_activities = len([log for log in logs if log.status == ActivityStatus.FAILED])
            
            # Count by activity type
            activity_type_counts = {}
            for log in logs:
                activity_type = log.activity_type.value
                activity_type_counts[activity_type] = activity_type_counts.get(activity_type, 0) + 1
            
            return {
                'total_activities': total_activities,
                'successful_activities': successful_activities,
                'failed_activities': failed_activities,
                'success_rate': (successful_activities / total_activities * 100) if total_activities > 0 else 0,
                'activity_type_counts': activity_type_counts
            }
            
        except Exception as e:
            logger.error(f"Failed to get activity stats: {e}")
            return {
                'total_activities': 0,
                'successful_activities': 0,
                'failed_activities': 0,
                'success_rate': 0,
                'activity_type_counts': {}
            }
