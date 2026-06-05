# routes/auth.py
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
from models import db, User, Todo, TodoList, ActivityLog
from datetime import datetime, timedelta
import re
import logging

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
logger = logging.getLogger(__name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, "Valid"

def log_activity(user_id, action, entity_type, entity_id=None, details=None, request_obj=None):
    """Log user activity"""
    try:
        ip_address = request_obj.remote_addr if request_obj else None
        user_agent = request_obj.user_agent.string if request_obj and hasattr(request_obj, 'user_agent') else None
        
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        db.session.rollback()

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['email', 'username', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': 'Missing required fields', 
            'required': required_fields
        }), 400
    
    # Validate email
    if not validate_email(data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Validate username
    if len(data['username']) < 3 or len(data['username']) > 80:
        return jsonify({'error': 'Username must be between 3 and 80 characters'}), 400
    
    # Validate password
    is_valid, message = validate_password(data['password'])
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Check if user exists
    existing_user = User.query.filter(
        (User.email == data['email']) | (User.username == data['username'])
    ).first()
    
    if existing_user:
        if existing_user.email == data['email']:
            return jsonify({'error': 'Email already registered'}), 409
        else:
            return jsonify({'error': 'Username already taken'}), 409
    
    # Create new user
    user = User(
        email=data['email'],
        username=data['username'],
        full_name=data.get('full_name', ''),
        avatar_url=data.get('avatar_url')
    )
    user.set_password(data['password'])
    
    # Set user preferences if provided
    if data.get('preferences'):
        user.set_preferences(data['preferences'])
    
    try:
        db.session.add(user)
        db.session.commit()
        
        # Create default list for user
        from models import TodoList
        default_list = TodoList(
            name='My Tasks',
            is_default=True,
            user_id=user.id,
            sort_order=0
        )
        db.session.add(default_list)
        db.session.commit()
        
        # Log registration
        log_activity(user.id, 'REGISTER', 'user', user.id, 'User registered', request)
        
        # Generate tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 86400  # 24 hours in seconds
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {str(e)}")
        return jsonify({'error': 'Failed to create user'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    if not data or not all(k in data for k in ('email', 'password')):
        return jsonify({'error': 'Email and password required'}), 400
    
    # Find user by email or username
    user = User.query.filter(
        (User.email == data['email']) | (User.username == data['email'])
    ).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid email/username or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated. Please contact support.'}), 403
    
    # Update last login
    user.update_last_login()
    
    # Log login
    log_activity(user.id, 'LOGIN', 'user', user.id, f"User logged in from {request.remote_addr}", request)
    
    # Generate tokens
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    # Get user completion rate
    total = Todo.query.filter_by(user_id=user.id).count()
    completed = Todo.query.filter_by(user_id=user.id, completed=True).count()
    completion_rate = round((completed / total * 100), 2) if total > 0 else 0.0
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
        'stats': {
            'completion_rate': completion_rate
        },
        'expires_in': 86400
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401
    
    new_access_token = create_access_token(identity=str(current_user_id))
    
    log_activity(current_user_id, 'REFRESH_TOKEN', 'auth', None, 'Token refreshed', request)
    
    return jsonify({
        'access_token': new_access_token,
        'expires_in': 86400
    }), 200

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user stats
    from models import Todo
    now = datetime.utcnow()
    pending = Todo.query.filter_by(user_id=current_user_id, completed=False, status='pending').count()
    completed_count = Todo.query.filter_by(user_id=current_user_id, completed=True).count()
    overdue = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == False,
        Todo.due_date < now,
        Todo.due_date.isnot(None)
    ).count()
    with_due = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == False,
        Todo.due_date.isnot(None)
    ).count()
    high_priority = Todo.query.filter_by(
        user_id=current_user_id, priority='high', completed=False
    ).count()

    stats = {
        'pending_count': pending,
        'completed_count': completed_count,
        'overdue_count': overdue,
        'with_due_date': with_due,
        'high_priority_count': high_priority
    }
    
    return jsonify({
        'user': user.to_dict(),
        'stats': stats
    }), 200

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    changes = []
    
    # Update fields
    if 'full_name' in data:
        old_value = user.full_name
        user.full_name = data['full_name']
        changes.append(f"full_name: {old_value} -> {data['full_name']}")
    
    if 'username' in data and data['username'] != user.username:
        # Check if username taken
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 409
        old_value = user.username
        user.username = data['username']
        changes.append(f"username: {old_value} -> {data['username']}")
    
    if 'avatar_url' in data:
        old_value = user.avatar_url
        user.avatar_url = data['avatar_url']
        changes.append(f"avatar_url updated")
    
    if 'preferences' in data:
        user.set_preferences(data['preferences'])
        changes.append(f"preferences updated")
    
    db.session.commit()
    
    # Log changes
    if changes:
        log_activity(current_user_id, 'UPDATE_PROFILE', 'user', user.id, 
                    f"Updated: {', '.join(changes)}", request)
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    }), 200

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if not all(k in data for k in ('current_password', 'new_password')):
        return jsonify({'error': 'Current password and new password required'}), 400
    
    # Verify current password
    if not user.check_password(data['current_password']):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    # Validate new password
    is_valid, message = validate_password(data['new_password'])
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Check if new password is same as old
    if user.check_password(data['new_password']):
        return jsonify({'error': 'New password must be different from current password'}), 400
    
    # Update password
    user.set_password(data['new_password'])
    db.session.commit()
    
    # Log password change
    log_activity(current_user_id, 'CHANGE_PASSWORD', 'user', user.id, 'Password changed', request)
    
    return jsonify({'message': 'Password changed successfully'}), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    current_user_id = get_jwt_identity()
    
    # Log logout
    log_activity(current_user_id, 'LOGOUT', 'auth', None, 'User logged out', request)
    
    # In production, add token to blacklist
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/reset-password-request', methods=['POST'])
def reset_password_request():
    """Request password reset (send email)"""
    data = request.get_json()
    
    if not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if user:
        # Generate reset token (in production, store in database with expiry)
        reset_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))
        
        # In production, send email with reset link
        # For now, return token for testing
        return jsonify({
            'message': 'If email exists, reset link will be sent',
            'reset_token': reset_token  # Remove in production
        }), 200
    else:
        # Don't reveal if email exists or not
        return jsonify({'message': 'If email exists, reset link will be sent'}), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    data = request.get_json()
    
    if not all(k in data for k in ('token', 'new_password')):
        return jsonify({'error': 'Token and new password required'}), 400
    
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(data['token'])
        user_id = decoded['sub']
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Invalid token'}), 400
        
        # Validate new password
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Update password
        user.set_password(data['new_password'])
        db.session.commit()
        
        log_activity(user_id, 'RESET_PASSWORD', 'user', user.id, 'Password reset via email', request)
        
        return jsonify({'message': 'Password reset successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        return jsonify({'error': 'Invalid or expired token'}), 400

@auth_bp.route('/deactivate', methods=['DELETE'])
@jwt_required()
def deactivate_account():
    """Deactivate user account"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify password for confirmation
    if not data.get('password') or not user.check_password(data['password']):
        return jsonify({'error': 'Password confirmation required'}), 401
    
    # Soft delete - deactivate account
    user.is_active = False
    db.session.commit()
    
    log_activity(current_user_id, 'DEACTIVATE_ACCOUNT', 'user', user.id, 'Account deactivated', request)
    
    return jsonify({'message': 'Account deactivated successfully'}), 200