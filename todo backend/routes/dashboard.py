# routes/dashboard.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Todo, TodoList, ActivityLog
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
logger = logging.getLogger(__name__)

@dashboard_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_dashboard_summary():
    """Get dashboard summary statistics"""
    current_user_id = get_jwt_identity()
    
    # Current date ranges
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Base query for todos (exclude archived)
    base_query = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.parent_todo_id == None,
        Todo.status != 'archived'
    )
    
    # Statistics
    stats = {
        'total_todos': base_query.count(),
        'completed_todos': base_query.filter_by(completed=True).count(),
        'pending_todos': base_query.filter_by(completed=False).count(),
        'completion_rate': 0,
        'overdue_todos': 0,
        'high_priority_count': base_query.filter_by(priority='high', completed=False).count(),
        'today_due': 0,
        'this_week_due': 0,
        'this_month_due': 0,
        'lists_count': 0,
        'active_lists': 0
    }
    
    # Calculate completion rate
    if stats['total_todos'] > 0:
        stats['completion_rate'] = round((stats['completed_todos'] / stats['total_todos']) * 100, 2)
    
    # Overdue todos (due date passed and not completed)
    stats['overdue_todos'] = base_query.filter(
        Todo.due_date < now,
        Todo.completed == False,
        Todo.due_date.isnot(None)
    ).count()
    
    # Today's due todos
    stats['today_due'] = base_query.filter(
        Todo.due_date >= today_start,
        Todo.due_date < today_end,
        Todo.completed == False
    ).count()
    
    # This week due
    stats['this_week_due'] = base_query.filter(
        Todo.due_date >= week_start,
        Todo.due_date < week_start + timedelta(days=7),
        Todo.completed == False
    ).count()
    
    # This month due
    stats['this_month_due'] = base_query.filter(
        Todo.due_date >= month_start,
        Todo.due_date < month_start + timedelta(days=32),
        Todo.completed == False
    ).count()
    
    # Lists statistics
    stats['lists_count'] = TodoList.query.filter_by(user_id=current_user_id).count()
    stats['active_lists'] = TodoList.query.filter_by(user_id=current_user_id, is_archived=False).count()
    
    # Completion rate already calculated above; remove MSSQL function call
    
    return jsonify(stats), 200

@dashboard_bp.route('/recent-activity', methods=['GET'])
@jwt_required()
def get_recent_activity():
    """Get recent user activities"""
    current_user_id = get_jwt_identity()
    
    limit = request.args.get('limit', 20, type=int)
    
    activities = ActivityLog.query.filter_by(user_id=current_user_id)\
        .order_by(ActivityLog.created_at.desc())\
        .limit(limit)\
        .all()
    
    return jsonify({
        'activities': [act.to_dict() for act in activities],
        'total': len(activities)
    }), 200

@dashboard_bp.route('/priority-breakdown', methods=['GET'])
@jwt_required()
def get_priority_breakdown():
    """Get todo breakdown by priority"""
    current_user_id = get_jwt_identity()
    
    priorities = ['low', 'medium', 'high']
    breakdown = []
    
    for priority in priorities:
        total = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.priority == priority,
            Todo.parent_todo_id == None,
            Todo.status != 'archived'
        ).count()
        
        completed = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.priority == priority,
            Todo.completed == True,
            Todo.parent_todo_id == None,
            Todo.status != 'archived'
        ).count()
        
        pending = total - completed
        
        breakdown.append({
            'priority': priority,
            'total': total,
            'completed': completed,
            'pending': pending,
            'completion_rate': round((completed / total * 100) if total > 0 else 0, 2)
        })
    
    return jsonify(breakdown), 200

@dashboard_bp.route('/weekly-progress', methods=['GET'])
@jwt_required()
def get_weekly_progress():
    """Get weekly progress data for charts"""
    current_user_id = get_jwt_identity()
    
    # Get last 7 days
    days = []
    for i in range(6, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        days.append(date)
    
    weekly_data = []
    for day in days:
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        created = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.created_at >= day_start,
            Todo.created_at < day_end
        ).count()
        
        completed = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.completed_at >= day_start,
            Todo.completed_at < day_end
        ).count()
        
        weekly_data.append({
            'date': day.isoformat(),
            'day_name': day.strftime('%A'),
            'created': created,
            'completed': completed
        })
    
    return jsonify(weekly_data), 200

@dashboard_bp.route('/monthly-progress', methods=['GET'])
@jwt_required()
def get_monthly_progress():
    """Get monthly progress for the last 6 months"""
    current_user_id = get_jwt_identity()
    
    months = []
    for i in range(5, -1, -1):
        month_date = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
        months.append(month_date)
    
    monthly_data = []
    for month in months:
        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month.month == 12:
            month_end = month.replace(year=month.year + 1, month=1, day=1)
        else:
            month_end = month.replace(month=month.month + 1, day=1)
        
        created = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.created_at >= month_start,
            Todo.created_at < month_end
        ).count()
        
        completed = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.completed_at >= month_start,
            Todo.completed_at < month_end
        ).count()
        
        monthly_data.append({
            'month': month_start.strftime('%B %Y'),
            'month_index': month_start.month,
            'year': month_start.year,
            'created': created,
            'completed': completed
        })
    
    return jsonify(monthly_data), 200

@dashboard_bp.route('/upcoming-todos', methods=['GET'])
@jwt_required()
def get_upcoming_todos():
    """Get upcoming todos (due in next 7 days)"""
    current_user_id = get_jwt_identity()
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_week = today_start + timedelta(days=8)
    
    upcoming = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == False,
        Todo.parent_todo_id == None,
        Todo.status != 'archived',
        Todo.due_date >= today_start,
        Todo.due_date < next_week
    ).order_by(Todo.due_date).limit(20).all()
    
    return jsonify({
        'upcoming_todos': [todo.to_dict() for todo in upcoming],
        'count': len(upcoming)
    }), 200

@dashboard_bp.route('/recent-completed', methods=['GET'])
@jwt_required()
def get_recent_completed():
    """Get recently completed todos (last 7 days)"""
    current_user_id = get_jwt_identity()
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    completed = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at >= week_ago,
        Todo.parent_todo_id == None
    ).order_by(Todo.completed_at.desc()).limit(20).all()
    
    return jsonify({
        'recent_completed': [todo.to_dict() for todo in completed],
        'count': len(completed)
    }), 200

@dashboard_bp.route('/productivity-tips', methods=['GET'])
@jwt_required()
def get_productivity_tips():
    """Get personalized productivity tips based on user data"""
    current_user_id = get_jwt_identity()
    
    # Get user statistics by calling the function directly
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base_query = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.parent_todo_id == None,
        Todo.status != 'archived'
    )
    stats = {
        'total_todos': base_query.count(),
        'completed_todos': base_query.filter_by(completed=True).count(),
        'pending_todos': base_query.filter_by(completed=False).count(),
        'overdue_todos': base_query.filter(
            Todo.due_date < now, Todo.completed == False, Todo.due_date.isnot(None)
        ).count(),
        'high_priority_count': base_query.filter(Todo.priority == 'high', Todo.completed == False).count(),
        'today_due': base_query.filter(
            Todo.due_date >= today_start,
            Todo.due_date < today_start + timedelta(days=1),
            Todo.completed == False
        ).count(),
        'completion_rate': 0
    }
    if stats['total_todos'] > 0:
        stats['completion_rate'] = round((stats['completed_todos'] / stats['total_todos']) * 100, 2)
    
    tips = []
    
    # Generate tips based on data
    if stats.get('overdue_todos', 0) > 5:
        tips.append({
            'type': 'warning',
            'title': 'Overdue Tasks',
            'message': f"You have {stats['overdue_todos']} overdue tasks. Consider rescheduling or breaking them down into smaller tasks.",
            'action': 'View overdue tasks'
        })
    
    if stats.get('completion_rate', 0) < 30 and stats.get('total_todos', 0) > 10:
        tips.append({
            'type': 'suggestion',
            'title': 'Low Completion Rate',
            'message': 'Try using the Pomodoro technique (25 minutes work, 5 minutes break) to improve productivity.',
            'action': 'Learn more'
        })
    
    if stats.get('high_priority_count', 0) > 3:
        tips.append({
            'type': 'suggestion',
            'title': 'High Priority Tasks',
            'message': f"You have {stats['high_priority_count']} high priority tasks. Focus on completing these first thing in the morning.",
            'action': 'View high priority tasks'
        })
    
    if stats.get('today_due', 0) > 0:
        tips.append({
            'type': 'reminder',
            'title': 'Tasks Due Today',
            'message': f"You have {stats['today_due']} tasks due today. Plan your day accordingly.",
            'action': 'View today\'s tasks'
        })
    
    if not tips:
        tips.append({
            'type': 'positive',
            'title': 'Great Job!',
            'message': 'You\'re on track with your tasks. Keep up the good work!',
            'action': 'Set new goals'
        })
    
    return jsonify({'tips': tips}), 200