"""
Authentication and authorization service.
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from ..models import AuthContext, JWTPayload, UserRole

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for validating Appwrite JWT and checking roles."""

    def __init__(self, jwt_secret: Optional[str] = None):
        """Initialize auth service."""
        self.jwt_secret = jwt_secret or os.getenv('APPWRITE_JWT_SECRET')
        
        # For development/testing, allow token-based auth
        self.allow_token_auth = os.getenv('ALLOW_TOKEN_AUTH', 'false').lower() == 'true'
        self.dev_tokens = {
            'admin': os.getenv('DEV_ADMIN_TOKEN'),
            'sop': os.getenv('DEV_SOP_TOKEN')
        }

    def validate_appwrite_jwt(self, token: str) -> Optional[AuthContext]:
        """
        Validate Appwrite JWT token and extract user context.
        """
        try:
            logger.info(f"Validating JWT token: {token[:50]}...")
            if not self.jwt_secret:
                # Use the same default secret as create_jwt_token
                self.jwt_secret = "default-jwt-secret-2025"
                logger.warning("JWT secret not configured, using default secret for validation")
            
            logger.info(f"Using JWT secret: {self.jwt_secret[:20]}...")
            
            # Decode JWT
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=['HS256'],
                options={'verify_exp': True}
            )
            logger.info(f"JWT payload decoded successfully: {payload}")
            
            # Extract user information
            user_id = payload.get('user_id') or payload.get('sub')
            if not user_id:
                logger.error("No user_id found in JWT payload")
                return None
            
            # Determine role from claims
            role = self._extract_role_from_claims(payload)
            
            # Extract organization for SOP users
            organization_website = None
            if role == UserRole.SOP:
                organization_website = payload.get('organization_website')
            
            return AuthContext(
                user_id=user_id,
                role=role,
                organization_website=organization_website
            )
            
        except ExpiredSignatureError:
            logger.error("JWT token has expired")
            return None
        except InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating JWT: {e}")
            return None

    def _extract_role_from_claims(self, payload: Dict[str, Any]) -> UserRole:
        """Extract user role from JWT claims."""
        # Check for explicit role claim
        role = payload.get('role')
        if role:
            try:
                return UserRole(role)
            except ValueError:
                pass
        
        # Check for custom claims
        custom_claims = payload.get('custom_claims', {})
        role = custom_claims.get('role')
        if role:
            try:
                return UserRole(role)
            except ValueError:
                pass
        
        # Check for labels (Appwrite user labels)
        labels = payload.get('labels', [])
        if 'admin' in labels:
            return UserRole.ADMIN
        elif 'sop' in labels:
            return UserRole.SOP
        
        # Default to SOP if no role found
        return UserRole.SOP

    def validate_token_auth(self, token: str) -> Optional[AuthContext]:
        """
        Validate simple token-based auth for development/testing.
        """
        if not self.allow_token_auth:
            return None
        
        try:
            if token == self.dev_tokens.get('admin'):
                return AuthContext(
                    user_id='dev-admin',
                    role=UserRole.ADMIN
                )
            elif token == self.dev_tokens.get('sop'):
                return AuthContext(
                    user_id='dev-sop',
                    role=UserRole.SOP,
                    organization_website='example.com'  # Default for testing
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating token auth: {e}")
            return None

    def validate_request_auth(self, headers: Dict[str, str]) -> Optional[AuthContext]:
        """
        Validate authentication from request headers.
        """
        try:
            # Try JWT from Authorization header
            auth_header = headers.get('Authorization', '')
            logger.info(f"Authorization header: {auth_header}")
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                logger.info(f"Extracted token: {token[:50]}...")
                context = self.validate_appwrite_jwt(token)
                logger.info(f"JWT validation result: {context}")
                if context:
                    return context
            
            # Try JWT from X-Appwrite-JWT header
            jwt_header = headers.get('X-Appwrite-JWT')
            if jwt_header:
                context = self.validate_appwrite_jwt(jwt_header)
                if context:
                    return context
            
            # Try token-based auth for development
            token_header = headers.get('X-Auth-Token')
            if token_header:
                context = self.validate_token_auth(token_header)
                if context:
                    return context
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating request auth: {e}")
            return None

    def require_admin(self, auth_context: Optional[AuthContext]) -> bool:
        """Check if user has admin role."""
        return auth_context is not None and auth_context.role == UserRole.ADMIN

    def require_sop(self, auth_context: Optional[AuthContext]) -> bool:
        """Check if user has SOP role."""
        return auth_context is not None and auth_context.role == UserRole.SOP

    def can_access_organization(
        self,
        auth_context: Optional[AuthContext],
        organization_website: str
    ) -> bool:
        """
        Check if user can access organization resources.
        Admin users can access all organizations.
        SOP users can only access their own organization.
        """
        if not auth_context:
            return False
        
        if auth_context.role == UserRole.ADMIN:
            return True
        
        if auth_context.role == UserRole.SOP:
            return auth_context.organization_website == organization_website
        
        return False

    def extract_user_id_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract user ID from request headers (for Appwrite function context).
        """
        try:
            # Try X-Appwrite-UserId header (set by Appwrite)
            user_id = headers.get('X-Appwrite-UserId')
            if user_id:
                return user_id
            
            # Try to extract from JWT
            auth_context = self.validate_request_auth(headers)
            if auth_context:
                return auth_context.user_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting user ID: {e}")
            return None

    def create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            'ok': False,
            'status': status_code,
            'error': {
                'code': 'AUTH_ERROR',
                'message': message
            }
        }

    def create_unauthorized_response(self) -> Dict[str, Any]:
        """Create unauthorized response."""
        return self.create_error_response(401, 'Unauthorized')

    def create_forbidden_response(self) -> Dict[str, Any]:
        """Create forbidden response."""
        return self.create_error_response(403, 'Forbidden')

    def create_organization_access_denied_response(self) -> Dict[str, Any]:
        """Create organization access denied response."""
        return self.create_error_response(403, 'Access denied to organization resources')

    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256 (for Appwrite compatibility)."""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_jwt_token(self, payload: Dict[str, Any], expires_in_hours: int = 24) -> str:
        """Create JWT token with payload."""
        if not self.jwt_secret:
            # Use a default secret if none is configured
            self.jwt_secret = "default-jwt-secret-2025"
            logger.warning("JWT secret not configured, using default secret")
        
        # Add standard claims
        now = datetime.utcnow()
        token_payload = {
            'iat': now,
            'exp': now + timedelta(hours=expires_in_hours),
            'iss': 'certificate-backend',
            **payload
        }
        
        return jwt.encode(token_payload, self.jwt_secret, algorithm='HS256')

    def create_user_in_appwrite(self, email: str, password: str, name: str, role: str, organization_website: str = None) -> Dict[str, Any]:
        """Create user in Appwrite Users collection using the Users API, or return existing user."""
        try:
            from appwrite.services.users import Users
            from appwrite.id import ID
            
            # Initialize Appwrite client
            from appwrite.client import Client
            client = Client()
            client.set_endpoint(os.getenv('APPWRITE_ENDPOINT', 'https://cloud.appwrite.io/v1'))
            client.set_project(os.getenv('APPWRITE_PROJECT_ID'))
            client.set_key(os.getenv('APPWRITE_API_KEY'))
            
            # Initialize Users service
            users = Users(client)
            
            # First, try to find existing user by email
            try:
                # Search for user by email
                existing_users = users.list(
                    search=email
                )
                
                if existing_users['total'] > 0:
                    # User exists, return existing user data
                    existing_user = existing_users['users'][0]
                    logger.info(f"User {email} already exists with ID {existing_user['$id']}")
                    
                    return {
                        'ok': True,
                        'data': {
                            '$id': existing_user['$id'],
                            'email': existing_user['email'],
                            'name': existing_user['name'],
                            'role': role,
                            'organization_website': organization_website,
                            'existing': True  # Flag to indicate this is an existing user
                        }
                    }
                    
            except Exception as search_error:
                # If search fails, continue with user creation
                logger.info(f"Could not search for existing user: {search_error}, proceeding with creation")
            
            # User doesn't exist, create new user
            user = users.create(
                user_id=ID.unique(),  # Auto-generate unique user ID
                email=email,
                password=password,    # Appwrite handles password hashing
                name=name
            )
            
            # Add role as a label to the user
            if role:
                users.update_labels(
                    user_id=user['$id'],
                    labels=[role]
                )
            
            # Add organization website to user preferences if provided
            if organization_website:
                users.update_prefs(
                    user_id=user['$id'],
                    prefs={
                        'role': role,
                        'organization_website': organization_website
                    }
                )
            else:
                users.update_prefs(
                    user_id=user['$id'],
                    prefs={'role': role}
                )
            
            logger.info(f"Successfully created new user {email} with ID {user['$id']}")
            
            return {
                'ok': True,
                'data': {
                    '$id': user['$id'],
                    'email': user['email'],
                    'name': user['name'],
                    'role': role,
                    'organization_website': organization_website,
                    'existing': False  # Flag to indicate this is a new user
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating/finding user in Appwrite: {e}")
            return {
                'ok': False,
                'error': str(e)
            }
