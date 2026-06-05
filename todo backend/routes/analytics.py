# routes/analytics.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Todo, ActivityLog
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import json
import logging

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')
logger = logging.getLogger(__name__)

@analytics_bp.route('/completion-trends', methods=['GET'])
@jwt_required()
def get_completion_trends():
    """Get todo completion trends over time"""
    current_user_id = get_jwt_identity()
    
    # Get date range parameter (default: last 30 days)
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily completion data using SQL Server date functions
    query = db.session.query(
        func.cast(Todo.completed_at, db.Date).label('date'),
        func.count(Todo.id).label('completed_count')
    ).filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at >= start_date
    ).group_by(func.cast(Todo.completed_at, db.Date)).order_by('date')
    
    results = query.all()
    
    trends = {
        'daily_completion': [{'date': str(r.date), 'count': r.completed_count} for r in results],
        'total_completed': sum(r.completed_count for r in results),
        'period_days': days,
        'average_per_day': round(sum(r.completed_count for r in results) / days if days > 0 else 0, 2)
    }
    
    return jsonify(trends), 200

@analytics_bp.route('/productivity-score', methods=['GET'])
@jwt_required()
def get_productivity_score():
    """Calculate overall productivity score"""
    current_user_id = get_jwt_identity()
    
    # Get data for last 30 days
    days = 30
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Factors for productivity score
    # 1. Completion rate (40%)
    # 2. Consistency (30%)
    # 3. Timeliness (20%)
    # 4. Task complexity (10%)
    
    total_todos = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.created_at >= start_date,
        Todo.parent_todo_id == None
    ).count()
    
    completed_todos = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at >= start_date,
        Todo.parent_todo_id == None
    ).count()
    
    # Completion rate score
    completion_rate = (completed_todos / total_todos * 100) if total_todos > 0 else 0
    completion_score = completion_rate * 0.4
    
    # Consistency score - days with activity
    active_days = db.session.query(
        func.date(ActivityLog.created_at).label('date')
    ).filter(
        ActivityLog.user_id == current_user_id,
        ActivityLog.created_at >= start_date,
        ActivityLog.action.in_(['CREATE', 'COMPLETE'])
    ).distinct().count()
    
    consistency_score = (active_days / days * 100) * 0.3
    
    # Timeliness score - tasks completed before due date
    on_time = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at <= Todo.due_date,
        Todo.due_date.isnot(None),
        Todo.completed_at >= start_date
    ).count()
    
    total_with_due = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.due_date.isnot(None),
        Todo.completed_at >= start_date
    ).count()
    
    timeliness_rate = (on_time / total_with_due * 100) if total_with_due > 0 else 100
    timeliness_score = timeliness_rate * 0.2
    
    # Complexity score - based on priority distribution
    high_priority_completed = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.priority == 'high',
        Todo.completed == True,
        Todo.completed_at >= start_date
    ).count()
    
    complexity_score = (high_priority_completed / completed_todos * 100) if completed_todos > 0 else 0
    complexity_score = complexity_score * 0.1
    
    # Total score
    total_score = completion_score + consistency_score + timeliness_score + complexity_score
    
    # Rating
    if total_score >= 90:
        rating = "Excellent"
    elif total_score >= 75:
        rating = "Good"
    elif total_score >= 60:
        rating = "Fair"
    elif total_score >= 40:
        rating = "Needs Improvement"
    else:
        rating = "Poor"
    
    return jsonify({
        'score': round(total_score, 2),
        'rating': rating,
        'components': {
            'completion_rate': {
                'score': round(completion_score, 2),
                'value': round(completion_rate, 2),
                'weight': 40
            },
            'consistency': {
                'score': round(consistency_score, 2),
                'value': round(active_days / days * 100, 2),
                'weight': 30
            },
            'timeliness': {
                'score': round(timeliness_score, 2),
                'value': round(timeliness_rate, 2),
                'weight': 20
            },
            'complexity': {
                'score': round(complexity_score, 2),
                'value': round(high_priority_completed / completed_todos * 100 if completed_todos > 0 else 0, 2),
                'weight': 10
            }
        }
    }), 200

@analytics_bp.route('/peak-hours', methods=['GET'])
@jwt_required()
def get_peak_hours():
    """Analyze peak productivity hours"""
    current_user_id = get_jwt_identity()
    
    # Analyze when user completes most tasks
    hour_distribution = db.session.query(
        extract('hour', Todo.completed_at).label('hour'),
        func.count(Todo.id).label('completed_count')
    ).filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at >= datetime.utcnow() - timedelta(days=90)
    ).group_by(extract('hour', Todo.completed_at)).order_by('hour').all()
    
    # Find peak hours
    distribution = [{'hour': int(r.hour), 'count': r.completed_count} for r in hour_distribution]
    
    if distribution:
        peak_hour = max(distribution, key=lambda x: x['count'])
        off_peak_hours = [h for h in distribution if h['count'] < peak_hour['count'] * 0.3]
    else:
        peak_hour = {'hour': 9, 'count': 0}
        off_peak_hours = []
    
    return jsonify({
        'hourly_distribution': distribution,
        'peak_productivity_hour': peak_hour['hour'],
        'peak_hour_count': peak_hour['count'],
        'recommended_work_hours': [9, 10, 11, 14, 15, 16],  # Recommended based on common patterns
        'off_peak_hours': off_peak_hours
    }), 200

@analytics_bp.route('/labels-analysis', methods=['GET'])
@jwt_required()
def get_labels_analysis():
    """Analyze productivity by labels/categories"""
    current_user_id = get_jwt_identity()
    
    from models import TodoLabel, TodoLabelAssociation

    labels = TodoLabel.query.filter_by(user_id=current_user_id).all()
    analysis = []
    for label in labels:
        total = db.session.query(Todo).join(TodoLabelAssociation).filter(
            TodoLabelAssociation.label_id == label.id,
            Todo.user_id == current_user_id
        ).count()
        completed = db.session.query(Todo).join(TodoLabelAssociation).filter(
            TodoLabelAssociation.label_id == label.id,
            Todo.user_id == current_user_id,
            Todo.completed == True
        ).count()

        analysis.append({
            'label': label.name,
            'color': label.color,
            'total_todos': total,
            'completed_todos': completed,
            'completion_rate': round((completed / total * 100) if total > 0 else 0, 2),
            'avg_completion_days': 0
        })
    
    return jsonify(analysis), 200

@analytics_bp.route('/forecast', methods=['GET'])
@jwt_required()
def get_forecast():
    """Predict future task completion based on historical data"""
    current_user_id = get_jwt_identity()
    
    # Get average completion rate per week for last 4 weeks
    weekly_data = []
    for i in range(4):
        week_start = datetime.utcnow() - timedelta(weeks=i+1)
        week_end = week_start + timedelta(days=7)
        
        completed = Todo.query.filter(
            Todo.user_id == current_user_id,
            Todo.completed == True,
            Todo.completed_at >= week_start,
            Todo.completed_at < week_end
        ).count()
        
        weekly_data.append(completed)
    
    # Simple forecast: average of last 4 weeks
    avg_weekly_completion = sum(weekly_data) / len(weekly_data) if weekly_data else 0
    
    # Predict next week's completion
    next_week_forecast = avg_weekly_completion
    
    # Get current pending tasks
    pending_count = Todo.query.filter_by(
        user_id=current_user_id,
        completed=False,
        parent_todo_id=None
    ).count()
    
    weeks_to_complete = pending_count / avg_weekly_completion if avg_weekly_completion > 0 else 0
    
    return jsonify({
        'forecast': {
            'next_week_prediction': round(next_week_forecast, 0),
            'weeks_to_complete_all': round(weeks_to_complete, 1),
            'confidence_level': 'medium'  # Based on data consistency
        },
        'historical_weekly_average': round(avg_weekly_completion, 2),
        'current_backlog': pending_count,
        'weekly_trend': weekly_data
    }), 200

@analytics_bp.route('/export-report', methods=['GET'])
@jwt_required()
def export_report():
    """Export full analytics report as JSON"""
    current_user_id = get_jwt_identity()
    
    # Collect all analytics data
    report = {
        'exported_at': datetime.utcnow().isoformat(),
        'user_id': current_user_id,
        'period': 'last_90_days',
        'data': {}
    }
    
    # Get trends
    trends_response = get_completion_trends()
    report['data']['completion_trends'] = trends_response[0].get_json()
    
    # Get productivity score
    score_response = get_productivity_score()
    report['data']['productivity_score'] = score_response[0].get_json()
    
    # Get peak hours
    hours_response = get_peak_hours()
    report['data']['peak_hours'] = hours_response[0].get_json()
    
    # Get label analysis
    labels_response = get_labels_analysis()
    report['data']['labels_analysis'] = labels_response[0].get_json()
    
    # Log export
    activity = ActivityLog(
        user_id=current_user_id,
        action='EXPORT_ANALYTICS',
        entity_type='report',
        details='Exported full analytics report'
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify(report), 200