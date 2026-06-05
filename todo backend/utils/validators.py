# utils/validators.py
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 120:
        return False, "Email must be less than 120 characters"
    
    return True, "Valid"

def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Valid"

def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username"""
    if not username:
        return False, "Username is required"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 80:
        return False, "Username must be less than 80 characters"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    return True, "Valid"

def validate_todo_title(title: str) -> Tuple[bool, str]:
    """Validate todo title"""
    if not title:
        return False, "Title is required"
    
    if len(title) < 1:
        return False, "Title must be at least 1 character"
    
    if len(title) > 200:
        return False, "Title must be less than 200 characters"
    
    return True, "Valid"

def validate_priority(priority: str) -> Tuple[bool, str]:
    """Validate priority value"""
    valid_priorities = ['low', 'medium', 'high']
    
    if not priority:
        return True, "Valid"  # Priority is optional
    
    if priority not in valid_priorities:
        return False, f"Priority must be one of: {', '.join(valid_priorities)}"
    
    return True, "Valid"

def validate_date(date_str: Optional[str]) -> Tuple[bool, str, Optional[datetime]]:
    """Validate date string and convert to datetime"""
    if not date_str:
        return True, "Valid", None
    
    try:
        # Try ISO format
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return True, "Valid", date_obj
    except ValueError:
        try:
            # Try alternative format
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return True, "Valid", date_obj
        except ValueError:
            return False, "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)", None

def validate_list_name(name: str) -> Tuple[bool, str]:
    """Validate list name"""
    if not name:
        return False, "List name is required"
    
    if len(name) < 1:
        return False, "List name must be at least 1 character"
    
    if len(name) > 100:
        return False, "List name must be less than 100 characters"
    
    return True, "Valid"

def validate_color(color: str) -> Tuple[bool, str]:
    """Validate hex color code"""
    if not color:
        return True, "Valid"  # Color is optional
    
    if not re.match(r'^#[0-9a-fA-F]{6}$', color):
        return False, "Color must be a valid hex code (e.g., #FF0000)"
    
    return True, "Valid"

def validate_todo_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Validate complete todo data"""
    errors = {}
    
    # Validate title
    if 'title' in data:
        valid, msg = validate_todo_title(data['title'])
        if not valid:
            errors['title'] = msg
    
    # Validate priority
    if 'priority' in data:
        valid, msg = validate_priority(data['priority'])
        if not valid:
            errors['priority'] = msg
    
    # Validate dates
    for date_field in ['due_date', 'reminder_date', 'start_date']:
        if date_field in data:
            valid, msg, _ = validate_date(data[date_field])
            if not valid:
                errors[date_field] = msg
    
    # Validate list_id
    if 'list_id' in data and data['list_id'] is not None:
        if not isinstance(data['list_id'], int) or data['list_id'] <= 0:
            errors['list_id'] = "List ID must be a positive integer"
    
    # Validate position
    if 'position' in data:
        if not isinstance(data['position'], int) or data['position'] < 0:
            errors['position'] = "Position must be a non-negative integer"
    
    return len(errors) == 0, errors

def validate_user_data(data: Dict[str, Any], is_update: bool = False) -> Tuple[bool, Dict[str, str]]:
    """Validate user data for registration/update"""
    errors = {}
    
    if not is_update or 'email' in data:
        valid, msg = validate_email(data.get('email', ''))
        if not valid:
            errors['email'] = msg
    
    if not is_update or 'username' in data:
        valid, msg = validate_username(data.get('username', ''))
        if not valid:
            errors['username'] = msg
    
    if not is_update or 'password' in data:
        if not is_update or (is_update and data.get('password')):
            valid, msg = validate_password(data.get('password', ''))
            if not valid:
                errors['password'] = msg
    
    # Validate full_name (optional)
    if 'full_name' in data and data['full_name']:
        if len(data['full_name']) > 100:
            errors['full_name'] = "Full name must be less than 100 characters"
    
    # Validate avatar_url (optional)
    if 'avatar_url' in data and data['avatar_url']:
        if not re.match(r'^https?://', data['avatar_url']):
            errors['avatar_url'] = "Avatar URL must start with http:// or https://"
    
    return len(errors) == 0, errors

def validate_pagination_params(page: int, per_page: int) -> Tuple[bool, Dict[str, str]]:
    """Validate pagination parameters"""
    errors = {}
    
    if page < 1:
        errors['page'] = "Page must be greater than 0"
    
    if per_page < 1 or per_page > 100:
        errors['per_page'] = "Per page must be between 1 and 100"
    
    return len(errors) == 0, errors

def sanitize_string(text: str) -> str:
    """Sanitize string input to prevent XSS"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Remove script tags content
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
    
    # Escape special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    return text.strip()

def is_valid_uuid(uuid_string: str) -> bool:
    """Check if string is valid UUID"""
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, uuid_string.lower()))