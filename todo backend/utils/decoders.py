from functools import wraps
from flask import request, jsonify, g, current_app
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
from models import db, User, ActivityLog
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, Any, Callable
import hashlib
import json

logger = logging.getLogger(__name__)

# Optional: Redis for production rate limiting
# redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

class RateLimiter:
    """Rate limiter using in-memory storage (use Redis in production)"""
    def __init__(self):
        self.requests = {}  # {client_id: [(timestamp, endpoint), ...]}
    
    def is_allowed(self, client_id: str, endpoint: str, limit: int, window: int) -> bool:
        """Check if request is allowed within rate limits"""
        now = time.time()
        key = f"{client_id}:{endpoint}"
        
        # Clean old entries
        if key in self.requests:
            self.requests[key] = [
                (ts, ep) for ts, ep in self.requests[key] 
                if now - ts < window and ep == endpoint
            ]
        else:
            self.requests[key] = []
        
        # Check limit
        if len(self.requests[key]) >= limit:
            return False
        
        # Add current request
        self.requests[key].append((now, endpoint))
        return True

# Global rate limiter instance
rate_limiter = RateLimiter()

def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # Verify JWT token
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            
            # Get user from database
            user = User.query.get(current_user_id)
            
            if not user:
                return jsonify({
                    'error': 'User not found',
                    'message': 'The user associated with this token no longer exists'
                }), 404
            
            if not user.is_active:
                return jsonify({
                    'error': 'Account deactivated',
                    'message': 'Your account has been deactivated. Please contact support.'
                }), 403
            
            # Store user in Flask's global context
            g.current_user = user
            g.current_user_id = current_user_id
            
            # Get additional claims if needed
            claims = get_jwt()
            g.token_claims = claims
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return jsonify({
                'error': 'Invalid or missing token',
                'message': 'Please provide a valid authentication token'
            }), 401
    
    return decorated

def optional_token(f):
    """Decorator that optionally validates token (doesn't require it)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=True)
            current_user_id = get_jwt_identity()
            
            if current_user_id:
                user = User.query.get(current_user_id)
                if user and user.is_active:
                    g.current_user = user
                    g.current_user_id = current_user_id
        except:
            # Token is invalid but that's fine since it's optional
            pass
        
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # First verify token
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check for admin role (you need to add is_admin field to User model)
        if not hasattr(user, 'is_admin') or not user.is_admin:
            logger.warning(f"Non-admin user {current_user_id} attempted admin access to {request.path}")
            return jsonify({
                'error': 'Admin privileges required',
                'message': 'You do not have permission to access this resource'
            }), 403
        
        g.current_user = user
        g.current_user_id = current_user_id
        
        return f(*args, **kwargs)
    
    return decorated

def rate_limit(limit: int = 100, window: int = 60, by_ip: bool = False):
    """
    Rate limiting decorator
    
    Args:
        limit: Maximum number of requests in the time window
        window: Time window in seconds
        by_ip: If True, rate limit by IP address instead of user ID
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Determine client identifier
            if by_ip:
                client_id = request.remote_addr
            else:
                try:
                    verify_jwt_in_request(optional=True)
                    client_id = str(get_jwt_identity()) or request.remote_addr
                except:
                    client_id = request.remote_addr
            
            # Use Redis in production for better performance
            # if redis_client:
            #     key = f"rate_limit:{client_id}:{request.endpoint}"
            #     current = redis_client.get(key)
            #     
            #     if current and int(current) >= limit:
            #         return jsonify({
            #             'error': 'Rate limit exceeded',
            #             'message': f'Maximum {limit} requests per {window} seconds',
            #             'retry_after': window
            #         }), 429
            #     
            #     pipe = redis_client.pipeline()
            #     pipe.incr(key)
            #     pipe.expire(key, window)
            #     pipe.execute()
            # else:
            #     # Fallback to in-memory rate limiter
            if not rate_limiter.is_allowed(client_id, request.endpoint, limit, window):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {limit} requests per {window} seconds',
                    'retry_after': window,
                    'limit': limit,
                    'window': window
                }), 429
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator

def log_request(f):
    """Log incoming requests decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get user ID if authenticated
        user_id = None
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
        except:
            pass
        
        # Log request details
        log_data = {
            'method': request.method,
            'path': request.path,
            'ip': request.remote_addr,
            'user_agent': request.user_agent.string if request.user_agent else None,
            'user_id': user_id,
            'endpoint': request.endpoint
        }
        
        # Log request body for non-sensitive endpoints (optional)
        if request.is_json and request.method in ['POST', 'PUT', 'PATCH']:
            data = request.get_json()
            # Mask sensitive data
            if data:
                masked_data = {k: ('***' if k in ['password', 'token', 'api_key'] else v) 
                              for k, v in data.items()}
                log_data['body'] = masked_data
        
        logger.info(f"Request: {json.dumps(log_data, default=str)}")
        
        start_time = time.time()
        
        try:
            # Execute the function
            response = f(*args, **kwargs)
            
            # Calculate response time
            elapsed_time = (time.time() - start_time) * 1000
            
            # Log response
            status_code = response[1] if isinstance(response, tuple) else 200
            logger.info(f"Response: {request.method} {request.path} - {status_code} - {elapsed_time:.2f}ms")
            
            return response
            
        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(f"Request failed: {request.method} {request.path} - {str(e)} - {elapsed_time:.2f}ms")
            raise
    
    return decorated

def validate_json(schema: Dict[str, Any] = None):
    """
    Validate JSON request body against schema
    
    Schema format:
    {
        'required': ['field1', 'field2'],
        'types': {
            'field1': str,
            'field2': int,
            'field3': list
        },
        'values': {
            'field1': ['value1', 'value2']  # Allowed values
        },
        'min_length': {
            'field1': 3
        },
        'max_length': {
            'field1': 100
        }
    }
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'error': 'Invalid content type',
                    'message': 'Request must be JSON'
                }), 400
            
            data = request.get_json()
            
            if data is None:
                return jsonify({
                    'error': 'Invalid JSON',
                    'message': 'Request body contains invalid JSON'
                }), 400
            
            if schema:
                errors = []
                
                # Check required fields
                for required_field in schema.get('required', []):
                    if required_field not in data:
                        errors.append(f"Missing required field: '{required_field}'")
                    elif data[required_field] is None:
                        errors.append(f"Field '{required_field}' cannot be null")
                
                # Check field types
                for field, expected_type in schema.get('types', {}).items():
                    if field in data and data[field] is not None:
                        if not isinstance(data[field], expected_type):
                            errors.append(
                                f"Field '{field}' must be of type {expected_type.__name__}, "
                                f"got {type(data[field]).__name__}"
                            )
                
                # Check allowed values
                for field, allowed_values in schema.get('values', {}).items():
                    if field in data and data[field] is not None:
                        if data[field] not in allowed_values:
                            errors.append(
                                f"Field '{field}' must be one of: {', '.join(map(str, allowed_values))}"
                            )
                
                # Check minimum length for strings
                for field, min_len in schema.get('min_length', {}).items():
                    if field in data and isinstance(data[field], str):
                        if len(data[field]) < min_len:
                            errors.append(
                                f"Field '{field}' must be at least {min_len} characters long"
                            )
                
                # Check maximum length for strings
                for field, max_len in schema.get('max_length', {}).items():
                    if field in data and isinstance(data[field], str):
                        if len(data[field]) > max_len:
                            errors.append(
                                f"Field '{field}' must be at most {max_len} characters long"
                            )
                
                # Check minimum value for numbers
                for field, min_val in schema.get('min_value', {}).items():
                    if field in data and isinstance(data[field], (int, float)):
                        if data[field] < min_val:
                            errors.append(
                                f"Field '{field}' must be at least {min_val}"
                            )
                
                # Check maximum value for numbers
                for field, max_val in schema.get('max_value', {}).items():
                    if field in data and isinstance(data[field], (int, float)):
                        if data[field] > max_val:
                            errors.append(
                                f"Field '{field}' must be at most {max_val}"
                            )
                
                # Custom validation function
                if 'custom' in schema and callable(schema['custom']):
                    custom_errors = schema['custom'](data)
                    if custom_errors:
                        errors.extend(custom_errors)
                
                if errors:
                    return jsonify({
                        'error': 'Validation failed',
                        'errors': errors
                    }), 400
            
            # Store validated data in g for use in route
            g.validated_data = data
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator

def handle_transaction(f):
    """Handle database transaction with automatic commit/rollback"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            logger.error(f"Transaction failed: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Database operation failed',
                'message': str(e) if current_app.debug else 'An error occurred while processing your request'
            }), 500
    
    return decorated

def cache_response(timeout: int = 300, key_prefix: str = None):
    """
    Cache response decorator (in-memory cache)
    For production, use Redis instead
    """
    cache = {}
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return f(*args, **kwargs)
            
            # Generate cache key
            if key_prefix:
                cache_key = f"{key_prefix}:{request.args}"
            else:
                # Include user ID in cache key for authenticated endpoints
                user_id = None
                try:
                    verify_jwt_in_request(optional=True)
                    user_id = get_jwt_identity()
                except:
                    pass
                
                cache_key = f"{request.path}:{user_id}:{request.args}"
            
            # Hash the cache key to avoid very long keys
            cache_key = hashlib.md5(cache_key.encode()).hexdigest()
            
            # Check cache
            if cache_key in cache:
                cached_time, cached_response = cache[cache_key]
                if time.time() - cached_time < timeout:
                    logger.debug(f"Cache hit for {request.path}")
                    # Return cached response (need to recreate response object)
                    return jsonify(cached_response), 200
            
            # Execute function
            response = f(*args, **kwargs)
            
            # Cache response if successful
            if isinstance(response, tuple):
                response_data, status_code = response
            else:
                response_data, status_code = response, 200
            
            if status_code == 200:
                # Convert response to serializable format if needed
                if hasattr(response_data, 'get_json'):
                    response_data = response_data.get_json()
                cache[cache_key] = (time.time(), response_data)
                logger.debug(f"Cached response for {request.path}")
            
            return response
        
        return decorated
    
    return decorator

def require_permission(permission: str):
    """Check if user has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Check user permissions (you need to implement permission system)
            # For now, only admin has all permissions
            if hasattr(user, 'is_admin') and user.is_admin:
                return f(*args, **kwargs)
            
            # You can implement granular permissions here
            # user_permissions = get_user_permissions(user.id)
            # if permission not in user_permissions:
            #     return jsonify({'error': 'Insufficient permissions'}), 403
            
            return jsonify({
                'error': 'Insufficient permissions',
                'message': f"You don't have permission to perform this action"
            }), 403
        
        return decorated
    
    return decorator

def track_activity(entity_type: str = None):
    """
    Automatically track user activity
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Execute the function first
            response = f(*args, **kwargs)
            
            # Track activity if user is authenticated
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                
                if user_id:
                    # Determine action based on HTTP method
                    action_map = {
                        'GET': 'VIEW',
                        'POST': 'CREATE',
                        'PUT': 'UPDATE',
                        'PATCH': 'UPDATE',
                        'DELETE': 'DELETE'
                    }
                    action = action_map.get(request.method, 'ACCESS')
                    
                    # Get entity ID from kwargs if available
                    entity_id = kwargs.get('id') or kwargs.get('todo_id') or kwargs.get('list_id')
                    
                    # Create activity log
                    activity = ActivityLog(
                        user_id=user_id,
                        action=action,
                        entity_type=entity_type or request.endpoint.split('.')[-1],
                        entity_id=entity_id,
                        details=f"{action} {request.path}",
                        ip_address=request.remote_addr,
                        user_agent=request.user_agent.string if request.user_agent else None
                    )
                    db.session.add(activity)
                    db.session.commit()
            except Exception as e:
                logger.error(f"Failed to track activity: {str(e)}")
                # Don't fail the request if activity logging fails
                db.session.rollback()
            
            return response
        
        return decorated
    
    return decorator

def retry_on_failure(max_retries: int = 3, delay: int = 1):
    """Retry function execution on failure"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed: {str(e)}")
            
            return jsonify({
                'error': 'Operation failed after retries',
                'message': str(last_exception)
            }), 500
        
        return decorated
    
    return decorator

def register_error_handlers(app):
    """Register global error handlers for the Flask app"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication is required to access this resource'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'error': 'Method not allowed',
            'message': f'The {request.method} method is not allowed for this endpoint'
        }), 405
    
    @app.errorhandler(409)
    def conflict(error):
        return jsonify({
            'error': 'Conflict',
            'message': str(error.description) if hasattr(error, 'description') else 'Resource conflict'
        }), 409
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        return jsonify({
            'error': 'Unprocessable entity',
            'message': 'The request was well-formed but could not be processed'
        }), 422
    
    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({
            'error': 'Too many requests',
            'message': 'Rate limit exceeded. Please try again later.',
            'retry_after': 60
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.'
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        return jsonify({
            'error': 'Service unavailable',
            'message': 'The service is temporarily unavailable. Please try again later.'
        }), 503

# Example usage schema for validation
TODO_SCHEMA = {
    'required': ['title'],
    'types': {
        'title': str,
        'description': str,
        'priority': str,
        'status': str,
        'list_id': int
    },
    'values': {
        'priority': ['low', 'medium', 'high'],
        'status': ['pending', 'in_progress', 'completed', 'archived']
    },
    'min_length': {
        'title': 1
    },
    'max_length': {
        'title': 200,
        'description': 5000
    }
}

USER_REGISTER_SCHEMA = {
    'required': ['email', 'username', 'password'],
    'types': {
        'email': str,
        'username': str,
        'password': str,
        'full_name': str
    },
    'min_length': {
        'username': 3,
        'password': 8
    },
    'max_length': {
        'email': 120,
        'username': 80,
        'password': 128,
        'full_name': 100
    }
}

USER_LOGIN_SCHEMA = {
    'required': ['email', 'password'],
    'types': {
        'email': str,
        'password': str
    }
}

LIST_SCHEMA = {
    'required': ['name'],
    'types': {
        'name': str,
        'color': str,
        'icon': str
    },
    'min_length': {
        'name': 1
    },
    'max_length': {
        'name': 100
    }
}