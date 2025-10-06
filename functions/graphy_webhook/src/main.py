"""
Graphy Webhook - Receives completion webhooks from Graphy platform.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
shared_dir = os.path.join(current_dir, 'shared')
sys.path.insert(0, current_dir)

from shared.models import WebhookPayload, WebhookEventModel, WebhookStatus
from shared.services.db import AppwriteClient
from shared.services.graphy import GraphyService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphyWebhookHandler:
    """Handles webhook events from Graphy platform."""

    def __init__(self):
        """Initialize webhook handler."""
        # Get Appwrite configuration with fallbacks
        endpoint = os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1')
        project_id = os.getenv('APPWRITE_PROJECT', '68cf04e30030d4b38d19')
        api_key = os.getenv('APPWRITE_API_KEY', 'standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142')
        
        logger.info(f"Database client config - endpoint: {endpoint}, project: {project_id}, api_key: {api_key[:20] if api_key else 'None'}...")
        
        # Initialize Appwrite client
        self.db = AppwriteClient(
            endpoint=endpoint,
            project_id=project_id,
            api_key=api_key
        )
        
        # Initialize Graphy service for signature verification
        self.graphy = GraphyService(
            api_base=os.getenv('GRAPHY_API_BASE', 'https://api.ongraphy.com'),
            api_key=os.getenv('GRAPHY_API_KEY'),
            merchant_id=os.getenv('GRAPHY_MERCHANT_ID')
        )

    def handle_webhook(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle incoming webhook from Graphy."""
        try:
            # Log webhook receipt
            logger.info(f"Received webhook: {json.dumps(request_data, default=str)}")
            
            # Validate webhook signature if provided
            signature = headers.get('X-Graphy-Signature') or headers.get('X-Webhook-Signature')
            if signature:
                webhook_secret = os.getenv('GRAPHY_WEBHOOK_SECRET')
                if webhook_secret:
                    payload_str = json.dumps(request_data, sort_keys=True)
                    if not self.graphy.verify_webhook_signature(payload_str, signature, webhook_secret):
                        logger.warning("Webhook signature verification failed")
                        return {
                            'ok': False,
                            'status': 401,
                            'error': {
                                'code': 'INVALID_SIGNATURE',
                                'message': 'Webhook signature verification failed'
                            }
                        }
                else:
                    logger.warning("Webhook signature provided but no secret configured")
            
            # Parse webhook payload
            try:
                webhook_payload = WebhookPayload(**request_data)
            except Exception as e:
                logger.error(f"Invalid webhook payload: {e}")
                return {
                    'ok': False,
                    'status': 400,
                    'error': {
                        'code': 'INVALID_PAYLOAD',
                        'message': f'Invalid webhook payload: {str(e)}'
                    }
                }
            
            # Check for duplicate webhook events
            if webhook_payload.event_id:
                existing_events = self.db.databases.list_documents(
                    database_id='main',
                    collection_id='webhook_events',
                    queries=[{
                        'attribute': 'event_id',
                        'operator': 'equal',
                        'value': webhook_payload.event_id
                    }]
                )
                
                if existing_events['documents']:
                    existing_event = existing_events['documents'][0]
                    if existing_event['status'] == WebhookStatus.PROCESSED.value:
                        logger.info(f"Webhook event {webhook_payload.event_id} already processed")
                        return {
                            'ok': True,
                            'status': 200,
                            'data': {
                                'message': 'Webhook already processed',
                                'event_id': webhook_payload.event_id
                            }
                        }
            
            # Store webhook event
            webhook_event_data = {
                'source': 'graphy',
                'payload': json.dumps(request_data),
                'course_id': webhook_payload.course_id,
                'email': webhook_payload.email,
                'event_id': webhook_payload.event_id,
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'status': WebhookStatus.RECEIVED.value,
                'attempts': 0
            }
            
            webhook_event = self.db.create_webhook_event(webhook_event_data)
            if not webhook_event:
                logger.error("Failed to create webhook event")
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'STORAGE_ERROR',
                        'message': 'Failed to store webhook event'
                    }
                }
            
            # Enqueue certificate worker
            try:
                self._enqueue_certificate_worker(webhook_event.id)
                logger.info(f"Certificate worker enqueued for webhook event {webhook_event.id}")
            except Exception as e:
                logger.error(f"Failed to enqueue certificate worker: {e}")
                # Update webhook status to failed
                self.db.update_webhook_event(webhook_event.id, {
                    'status': WebhookStatus.FAILED.value,
                    'attempts': 1
                })
                return {
                    'ok': False,
                    'status': 500,
                    'error': {
                        'code': 'ENQUEUE_ERROR',
                        'message': 'Failed to enqueue certificate processing'
                    }
                }
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Webhook received and queued for processing',
                    'event_id': webhook_event.id
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return {
                'ok': False,
                'status': 500,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Internal server error'
                }
            }

    def _enqueue_certificate_worker(self, webhook_event_id: str) -> None:
        """Enqueue certificate worker for processing."""
        try:
            # Method 1: Direct function invocation (if available in Appwrite)
            # This would typically use Appwrite's function execution API
            function_id = os.getenv('CERTIFICATE_WORKER_FUNCTION_ID')
            if function_id:
                # Use Appwrite function execution
                from appwrite.services.functions import Functions
                functions = Functions(self.db.client)
                
                functions.create_execution(
                    function_id=function_id,
                    data=json.dumps({'webhook_event_id': webhook_event_id})
                )
                return
            
            # Method 2: HTTP call to certificate worker endpoint
            worker_url = os.getenv('CERTIFICATE_WORKER_URL')
            if worker_url:
                import requests
                response = requests.post(
                    worker_url,
                    json={'webhook_event_id': webhook_event_id},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                if response.status_code not in [200, 201, 202]:
                    raise Exception(f"Certificate worker returned status {response.status_code}")
                return
            
            # Method 3: Direct processing (synchronous)
            # This is a fallback for development/testing
            logger.warning("No certificate worker configured, processing synchronously")
            self._process_certificate_sync(webhook_event_id)
            
        except Exception as e:
            logger.error(f"Error enqueuing certificate worker: {e}")
            raise

    def _process_certificate_sync(self, webhook_event_id: str) -> None:
        """Process certificate synchronously (fallback method)."""
        try:
            # Import certificate worker logic
            from certificate_worker import CertificateWorker
            
            worker = CertificateWorker()
            result = worker.process_webhook_event(webhook_event_id)
            
            if not result['ok']:
                raise Exception(f"Certificate processing failed: {result.get('error', 'Unknown error')}")
                
        except ImportError:
            logger.error("Certificate worker not available for synchronous processing")
            raise Exception("Certificate worker not available")
        except Exception as e:
            logger.error(f"Error in synchronous certificate processing: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        try:
            # Test database connection
            self.db.list_courses(limit=1)
            
            # Test Graphy connection
            graphy_health = self.graphy.health_check()
            
            return {
                'ok': True,
                'status': 200,
                'data': {
                    'message': 'Webhook handler is healthy',
                    'database': 'connected',
                    'graphy': 'connected' if graphy_health.get('ok') else 'disconnected'
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
        
        # Get headers
        headers = {}
        if hasattr(context.req, 'headers'):
            headers = dict(context.req.headers)
        
        # Check for health check
        if request_data.get('action') == 'health':
            handler = GraphyWebhookHandler()
            result = handler.health_check()
            return context.res.json(result)
        
        # Initialize handler
        handler = GraphyWebhookHandler()
        
        # Handle webhook
        response = handler.handle_webhook(request_data, headers)
        
        return context.res.json(response)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)
