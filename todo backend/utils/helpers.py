# utils/helpers.py
from models import db, User, Todo, TodoList, ActivityLog
from datetime import datetime, timedelta, timezone
import re
from functools import wraps
import hashlib
import secrets
import string
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def generate_api_key() -> str:
    """Generate a secure API key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

def hash_string(text: str) -> str:
    """Create SHA-256 hash of a string"""
    return hashlib.sha256(text.encode()).hexdigest()

def initialize_default_data():
    """Initialize default data for the application"""
    try:
        # Check if admin user exists
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = User(
                email='admin@example.com',
                username='admin',
                full_name='System Administrator',
                is_active=True
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin user created")
            
            # Create default list for admin
            default_list = TodoList(
                name='My Tasks',
                is_default=True,
                user_id=admin.id,
                sort_order=0
            )
            db.session.add(default_list)
            db.session.commit()
            logger.info("Default list created for admin")
        
        # Create system activity log
        system_activity = ActivityLog(
            user_id=1,  # Assuming admin ID is 1
            action='SYSTEM_START',
            entity_type='system',
            details='Application initialized with default data'
        )
        db.session.add(system_activity)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error initializing default data: {str(e)}")
        db.session.rollback()

def format_response(data: Any, message: str = None, status: str = 'success') -> Dict:
    """Format API response consistently"""
    response = {
        'status': status,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    
    if message:
        response['message'] = message
    
    return response

def calculate_completion_rate(user_id: int, days: int = 30) -> float:
    """Calculate user's completion rate for given period"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    total = Todo.query.filter(
        Todo.user_id == user_id,
        Todo.created_at >= start_date,
        Todo.parent_todo_id == None
    ).count()
    
    completed = Todo.query.filter(
        Todo.user_id == user_id,
        Todo.completed == True,
        Todo.completed_at >= start_date,
        Todo.parent_todo_id == None
    ).count()
    
    if total == 0:
        return 0.0
    
    return round((completed / total) * 100, 2)

def get_streak_count(user_id: int) -> int:
    """Calculate current streak of consecutive days with completed tasks"""
    streak = 0
    current_date = datetime.utcnow().date()
    
    while True:
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        completed_count = Todo.query.filter(
            Todo.user_id == user_id,
            Todo.completed == True,
            Todo.completed_at >= day_start,
            Todo.completed_at < day_end
        ).count()
        
        if completed_count > 0:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break
    
    return streak

def generate_password_reset_token(user_id: int) -> str:
    """Generate password reset token"""
    # Simple token generation - in production use JWT with expiry
    timestamp = datetime.utcnow().timestamp()
    token_data = f"{user_id}:{timestamp}:{secrets.token_urlsafe(16)}"
    return hash_string(token_data)

def send_email(to_email: str, subject: str, body: str, is_html: bool = False):
    """Send email (placeholder - implement with your email service)"""
    # In production, integrate with SendGrid, AWS SES, or SMTP
    logger.info(f"Email would be sent to {to_email}: {subject}")
    logger.debug(f"Email body: {body}")
    # Return True for now
    return True

def validate_and_sanitize_input(data: Dict, allowed_fields: list) -> Dict:
    """Validate and sanitize input data"""
    sanitized = {}
    
    for field in allowed_fields:
        if field in data:
            value = data[field]
            
            # Sanitize strings
            if isinstance(value, str):
                value = value.strip()
                # Remove potential XSS
                value = value.replace('<', '&lt;').replace('>', '&gt;')
            
            sanitized[field] = value
    
    return sanitized

def paginate_query(query, page: int = 1, per_page: int = 20):
    """Helper function to paginate SQLAlchemy queries"""
    if page < 1:
        page = 1
    
    if per_page < 1:
        per_page = 20
    elif per_page > 100:
        per_page = 100
    
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        'items': paginated.items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev
        }
    }

def parse_date_range(date_range: str) -> tuple:
    """Parse date range string and return start and end dates"""
    now = datetime.utcnow()
    
    ranges = {
        'today': (now.replace(hour=0, minute=0, second=0, microsecond=0), 
                 now.replace(hour=23, minute=59, second=59, microsecond=999999)),
        'yesterday': ((now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                     (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)),
        'this_week': (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0),
        'last_week': (now - timedelta(days=now.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0),
        'this_month': now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        'last_month': (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    }
    
    if date_range in ranges:
        return ranges[date_range]
    
    # Try to parse custom range: "2024-01-01,2024-01-31"
    if ',' in date_range:
        start_str, end_str = date_range.split(',')
        try:
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            return (start, end)
        except:
            pass
    
    # Default to last 30 days
    return (now - timedelta(days=30), now)

def log_user_action(user_id: int, action: str, entity_type: str, 
                   entity_id: int = None, details: str = None, 
                   request_obj = None):
    """Log user action to database"""
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
        return True
    except Exception as e:
        logger.error(f"Error logging action: {str(e)}")
        db.session.rollback()
        return False

def mask_sensitive_data(data: Dict) -> Dict:
    """Mask sensitive data in logs"""
    masked = data.copy()
    
    sensitive_fields = ['password', 'token', 'api_key', 'secret']
    
    for field in sensitive_fields:
        if field in masked:
            masked[field] = '***'
    
    return masked

def convert_to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC"""
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string to max length"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."

def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text"""
    # Convert to lowercase
    slug = text.lower()
    
    # Replace spaces with hyphens
    slug = slug.replace(' ', '-')
    
    # Remove special characters
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Remove multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Trim hyphens from ends
    slug = slug.strip('-')
    
    return slug

def calculate_priority_score(priority: str, due_date: Optional[datetime], completed: bool) -> int:
    """Calculate priority score for sorting"""
    if completed:
        return 0
    
    # Base priority scores
    priority_scores = {
        'high': 100,
        'medium': 60,
        'low': 30
    }
    
    score = priority_scores.get(priority, 50)
    
    # Add urgency for due dates
    if due_date:
        now = datetime.utcnow()
        days_until_due = (due_date - now).days
        
        if days_until_due < 0:
            score += 50  # Overdue
        elif days_until_due == 0:
            score += 40  # Due today
        elif days_until_due <= 2:
            score += 20  # Due soon
        elif days_until_due <= 7:
            score += 10   # Due this week
    
    return score