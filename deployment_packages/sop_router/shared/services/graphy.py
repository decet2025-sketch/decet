"""
Graphy API service wrapper with safe retries.
"""

import json
import logging
import time
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models import GraphyEnrollmentRequest, GraphyEnrollmentResponse

logger = logging.getLogger(__name__)


class GraphyService:
    """Graphy API service with retry logic and error handling."""

    def __init__(self, api_base: str, api_key: str, merchant_id: str = None, max_retries: int = 3):
        """Initialize Graphy/Spayee service."""
        # Default to Spayee API if not specified
        if not api_base or api_base == 'https://api.ongraphy.com':
            self.api_base = 'https://api.spayee.com'
        else:
            self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.merchant_id = merchant_id
        self.max_retries = max_retries
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers - Graphy uses different auth methods
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Certificate-Backend/1.0'
        })

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, use_auth: bool = True) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        url = f"{self.api_base}{endpoint}"
        
        # Prepare request parameters
        params = {}
        if use_auth and self.merchant_id:
            params['mid'] = self.merchant_id
            params['key'] = self.api_key
        
        try:
            if method.upper() == 'GET':
                # Merge params with data for GET requests
                if data:
                    params.update(data)
                logger.info(f"Graphy API GET request - URL: {url}, Params: {params}")
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, params=params, timeout=30)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, params=params, timeout=30)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Log request details
            logger.info(f"Graphy API {method} {url} - Status: {response.status_code}")
            logger.info(f"Response content: {response.text[:500]}")  # Log first 500 chars
            
            # Handle response
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    response_data = {"raw_response": response.text}
                
                return {
                    'ok': True,
                    'data': response_data,
                    'status_code': response.status_code
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                    elif 'errors' in error_data:
                        error_msg = str(error_data['errors'])
                except:
                    error_msg = response.text or error_msg
                
                return {
                    'ok': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Graphy API timeout for {method} {url}")
            return {
                'ok': False,
                'error': 'Request timeout',
                'status_code': 408
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Graphy API connection error for {method} {url}")
            return {
                'ok': False,
                'error': 'Connection error',
                'status_code': 503
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Graphy API request error for {method} {url}: {e}")
            return {
                'ok': False,
                'error': str(e),
                'status_code': 500
            }
        except Exception as e:
            logger.error(f"Unexpected error in Graphy API request: {e}")
            return {
                'ok': False,
                'error': 'Internal error',
                'status_code': 500
            }

    def enroll_learner(self, request: GraphyEnrollmentRequest) -> GraphyEnrollmentResponse:
        """
        Enroll a learner in a course using Spayee API.
        
        Based on Spayee API: https://api.spayee.com/public/v1/assign
        """
        try:
            # Prepare enrollment data for Spayee API
            enrollment_data = {
                'mid': self.merchant_id,
                'key': self.api_key,
                'email': request.email,
                'productId': request.course_id,
                'countryCode': request.metadata.get('countryCode', 'IN') if request.metadata else 'IN',
                'phone': request.metadata.get('phone', '') if request.metadata else '',
                'utmSource': request.metadata.get('utmSource', '') if request.metadata else '',
                'utmContent': request.metadata.get('utmContent', '') if request.metadata else '',
                'utmTerm': request.metadata.get('utmTerm', '') if request.metadata else '',
                'utmCampaign': request.metadata.get('utmCampaign', '') if request.metadata else '',
                'utmMedium': request.metadata.get('utmMedium', '') if request.metadata else '',
                'eventId': request.metadata.get('eventId', '') if request.metadata else '',
                'extPG': request.metadata.get('extPG', '') if request.metadata else '',
                'extPaymentId': request.metadata.get('extPaymentId', '') if request.metadata else ''
            }
            
            # Make API call to Spayee enrollment endpoint
            url = f"{self.api_base}/public/v1/assign"
            
            # Use form-encoded data for Spayee API
            response = self.session.post(
                url,
                data=enrollment_data,  # Use data instead of json for form-encoded
                timeout=30
            )
            
            logger.info(f"Spayee API POST {url} - Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json() if response.content else {}
                except json.JSONDecodeError:
                    response_data = {"raw_response": response.text}
                
                # Check if enrollment was successful
                if response_data.get('status') == 'success':
                    return GraphyEnrollmentResponse(
                        ok=True,
                        enrollment_id=response_data.get('enrollmentId') or response_data.get('id')
                    )
                else:
                    return GraphyEnrollmentResponse(
                        ok=False,
                        error=response_data.get('message', 'Enrollment failed')
                    )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_data.get('error', error_msg))
                except:
                    error_msg = response.text or error_msg
                
                return GraphyEnrollmentResponse(
                    ok=False,
                    error=error_msg
                )
                
        except Exception as e:
            logger.error(f"Error in enroll_learner: {e}")
            return GraphyEnrollmentResponse(
                ok=False,
                error=f"Enrollment failed: {str(e)}"
            )

    def get_products(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get all products (courses) from Graphy."""
        try:
            result = self._make_request(
                'GET',
                '/public/v1/products',
                {'limit': limit, 'offset': offset}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return {
                'ok': False,
                'error': f"Failed to get products: {str(e)}"
            }

    def get_product_info(self, product_id: str) -> Dict[str, Any]:
        """Get specific product (course) information from Graphy."""
        try:
            result = self._make_request(
                'GET',
                f'/public/v1/products/{product_id}'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting product info for {product_id}: {e}")
            return {
                'ok': False,
                'error': f"Failed to get product info: {str(e)}"
            }

    def get_learner_progress(self, product_id: str, email: str) -> Dict[str, Any]:
        """Get learner progress from Graphy."""
        try:
            result = self._make_request(
                'GET',
                f'/public/v1/products/{product_id}/learners/{email}/progress'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting learner progress for {product_id}/{email}: {e}")
            return {
                'ok': False,
                'error': f"Failed to get learner progress: {str(e)}"
            }

    def get_learner_enrollments(self, email: str) -> Dict[str, Any]:
        """Get all enrollments for a learner."""
        try:
            result = self._make_request(
                'GET',
                f'/public/v1/learners/{email}/enrollments'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting learner enrollments for {email}: {e}")
            return {
                'ok': False,
                'error': f"Failed to get learner enrollments: {str(e)}"
            }

    def get_learner_data(self, email: str) -> Dict[str, Any]:
        """Get learner data with all courses and progress."""
        try:
            # Use the learners API endpoint with courseInfo parameter
            # The Graphy API expects the query parameter to be JSON-encoded
            result = self._make_request(
                'GET',
                '/public/v2/learners',
                {
                    'query': json.dumps({'email': email}),  # JSON-encode the query
                    'courseInfo': 'true',  # Include course information
                    'limit': 1  # We only need one result
                }
            )
            
            if result['ok'] and 'data' in result['data']:
                learners = result['data']['data']
                if learners:
                    # Return the first (and should be only) learner
                    return {
                        'ok': True,
                        'data': learners[0]
                    }
                else:
                    return {
                        'ok': False,
                        'error': f'Learner with email {email} not found'
                    }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error getting learner data for {email}: {e}")
            return {
                'ok': False,
                'error': f"Failed to get learner data: {str(e)}"
            }

    def get_completion_status(self, product_id: str, email: str) -> Dict[str, Any]:
        """Get course completion status for a learner."""
        try:
            result = self._make_request(
                'GET',
                f'/public/v1/products/{product_id}/learners/{email}/completion'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting completion status for {product_id}/{email}: {e}")
            return {
                'ok': False,
                'error': f"Failed to get completion status: {str(e)}"
            }

    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """
        Verify webhook signature from Graphy.
        
        This is a placeholder implementation. The actual signature verification
        should be implemented based on Graphy's webhook signature method.
        """
        try:
            # Placeholder implementation - replace with actual Graphy signature verification
            # Common methods include HMAC-SHA256, HMAC-SHA1, etc.
            
            import hmac
            import hashlib
            
            # Example HMAC-SHA256 verification
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Remove 'sha256=' prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """Check API health (Graphy/Spayee)."""
        try:
            # Try to get products with limit 1 to test API connectivity
            # Use different endpoints based on API base
            if 'spayee.com' in self.api_base:
                # For Spayee, we can't easily test without a specific endpoint
                # Just test basic connectivity
                result = self._make_request('GET', '/public/v1/products', {'limit': 1})
                api_name = 'Spayee'
            else:
                # For Graphy
                result = self._make_request('GET', '/public/v1/products', {'limit': 1})
                api_name = 'Graphy'
            
            if result['ok']:
                return {
                    'ok': True,
                    'status': 'connected',
                    'message': f'{api_name} API is accessible'
                }
            else:
                return {
                    'ok': False,
                    'status': 'disconnected',
                    'error': result.get('error', 'Unknown error')
                }
            
        except Exception as e:
            logger.error(f"Error in API health check: {e}")
            return {
                'ok': False,
                'status': 'disconnected',
                'error': f"Health check failed: {str(e)}"
            }

    def get_webhook_events(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get webhook events from Graphy."""
        try:
            result = self._make_request(
                'GET',
                '/public/v1/webhooks/events',
                {'limit': limit, 'offset': offset}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting webhook events: {e}")
            return {
                'ok': False,
                'error': f"Failed to get webhook events: {str(e)}"
            }

    def get_analytics(self, product_id: str = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Get analytics data from Graphy."""
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date
                
            result = self._make_request(
                'GET',
                '/public/v1/analytics',
                params
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {
                'ok': False,
                'error': f"Failed to get analytics: {str(e)}"
            }

    def __del__(self):
        """Cleanup session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()
