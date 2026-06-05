from flask import Blueprint

from .auth import auth_bp
from .todos import todos_bp
from .lists import lists_bp
from .dashboard import dashboard_bp
from .analytics import analytics_bp
from .chatbot import chatbot_bp

__all__ = ['auth_bp', 'todos_bp', 'lists_bp', 'dashboard_bp', 'analytics_bp', 'chatbot_bp']
