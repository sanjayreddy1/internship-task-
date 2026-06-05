# utils/decorators.py
from functools import wraps
from flask import request, jsonify, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from models import User, db
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)

def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_active:
                return jsonify({'error': 'Account is deactivated'}), 403
            
            g.current_user = user
            g.current_user_id = current_user_id
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return jsonify({'error': 'Invalid or missing token'}), 401
    
    return decorated

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        # Check for admin role - you can add an 'is_admin' field to User model
        if not user or not hasattr(user, 'is_admin') or not user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

def rate_limit(limit=100, window=60):
    """Rate limiting decorator"""
    def decorator(f):
        # Store request counts in memory (use Redis in production)
        request_counts = {}
        
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get client identifier (IP or user ID if authenticated)
            client_id = request.remote_addr
            
            try:
                verify_jwt_in_request()
                client_id = str(get_jwt_identity())
            except:
                pass
            
            now = time.time()
            
            # Clean old entries
            request_counts[client_id] = [
                timestamp for timestamp in request_counts.get(client_id, [])
                if now - timestamp < window
            ]
            
            # Check limit
            if len(request_counts.get(client_id, [])) >= limit:
                return jsonify({
                    'error': f'Rate limit exceeded. Maximum {limit} requests per {window} seconds.'
                }), 429
            
            # Add current request
            if client_id not in request_counts:
                request_counts[client_id] = []
            request_counts[client_id].append(now)
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator

def log_request(f):
    """Log incoming requests decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Log request details
        logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
        
        # Log request body for debugging (optional)
        if request.is_json and request.get_json():
            # Mask sensitive data
            data = request.get_json()
            if 'password' in data:
                data['password'] = '***'
            logger.debug(f"Request data: {data}")
        
        start_time = time.time()
        
        # Execute the function
        response = f(*args, **kwargs)
        
        # Log response time
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"Response time: {elapsed_time:.2f}ms")
        
        return response
    
    return decorated

def validate_json(schema=None):
    """Validate JSON request body against schema"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            
            if schema:
                # Simple schema validation
                for required_field in schema.get('required', []):
                    if required_field not in data:
                        return jsonify({
                            'error': f'Missing required field: {required_field}'
                        }), 400
                
                for field, field_type in schema.get('types', {}).items():
                    if field in data and not isinstance(data[field], field_type):
                        return jsonify({
                            'error': f'Field {field} must be of type {field_type.__name__}'
                        }), 400
            
            return f(*args, **kwargs)
        
        return decorated
    
    return decorator

def handle_transaction(f):
    """Handle database transaction decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            logger.error(f"Transaction failed: {str(e)}")
            return jsonify({'error': 'Database operation failed', 'details': str(e)}), 500
    
    return decorated

def cache_response(timeout=300):
    """Simple in-memory cache decorator"""
    cache = {}
    
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Create cache key
            cache_key = f"{request.path}:{request.args}"
            
            # Check cache
            if cache_key in cache:
                cached_time, cached_response = cache[cache_key]
                if time.time() - cached_time < timeout:
                    return cached_response
            
            # Execute function
            response = f(*args, **kwargs)
            
            # Cache response (only for successful GET requests)
            if request.method == 'GET' and response[1] == 200:
                cache[cache_key] = (time.time(), response)
            
            return response
        
        return decorated
    
    return decorator

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request', 'details': str(error)}), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized'}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden'}), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405
    
    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({'error': 'Too many requests'}), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({'error': 'Internal server error'}), 500