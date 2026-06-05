# routes/lists.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, TodoList, Todo, ActivityLog
from datetime import datetime
from sqlalchemy import func
import logging

lists_bp = Blueprint('lists', __name__, url_prefix='/api/lists')
logger = logging.getLogger(__name__)

def log_list_activity(user_id, action, list_id, details=None, request_obj=None):
    """Log list activity"""
    try:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type='list',
            entity_id=list_id,
            details=details,
            ip_address=request_obj.remote_addr if request_obj else None,
            user_agent=request_obj.user_agent.string if request_obj and hasattr(request_obj, 'user_agent') else None
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging list activity: {str(e)}")
        db.session.rollback()

@lists_bp.route('/', methods=['GET'])
@jwt_required()
def get_lists():
    """Get all todo lists for current user"""
    current_user_id = get_jwt_identity()
    
    # Get all non-archived lists
    lists = TodoList.query.filter_by(
        user_id=current_user_id,
        is_archived=False
    ).order_by(TodoList.sort_order, TodoList.created_at).all()
    
    # Get archived lists separately
    archived_lists = TodoList.query.filter_by(
        user_id=current_user_id,
        is_archived=True
    ).order_by(TodoList.updated_at.desc()).all()
    
    # Get statistics for each list (exclude archived)
    for todo_list in lists:
        todo_list.todo_count = todo_list.todos.filter(Todo.status != 'archived', Todo.completed == False).count()
        todo_list.total_todos = todo_list.todos.filter(Todo.status != 'archived').count()
        todo_list.completed_todos = todo_list.todos.filter(Todo.status != 'archived', Todo.completed == True).count()
    
    return jsonify({
        'lists': [list_obj.to_dict() for list_obj in lists],
        'archived_lists': [list_obj.to_dict() for list_obj in archived_lists],
        'total_lists': len(lists),
        'total_archived': len(archived_lists)
    }), 200

@lists_bp.route('/', methods=['POST'])
@jwt_required()
def create_list():
    """Create a new todo list"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'List name is required'}), 400
    
    # Check for duplicate list name
    existing = TodoList.query.filter_by(
        user_id=current_user_id,
        name=data['name'],
        is_archived=False
    ).first()
    
    if existing:
        return jsonify({'error': 'A list with this name already exists'}), 409
    
    # Get max sort order
    max_order = db.session.query(func.max(TodoList.sort_order)).filter_by(
        user_id=current_user_id
    ).scalar() or 0
    
    todo_list = TodoList(
        name=data['name'],
        color=data.get('color', '#6366f1'),
        icon=data.get('icon', 'list'),
        sort_order=max_order + 1,
        user_id=current_user_id,
        is_default=False
    )
    
    db.session.add(todo_list)
    db.session.commit()
    
    # Log activity
    log_list_activity(current_user_id, 'CREATE', todo_list.id, 
                     f"Created list: {todo_list.name}", request)
    
    return jsonify({
        'message': 'List created successfully',
        'list': todo_list.to_dict()
    }), 201

@lists_bp.route('/<int:list_id>', methods=['GET'])
@jwt_required()
def get_list(list_id):
    """Get single list with its todos"""
    current_user_id = get_jwt_identity()
    
    todo_list = TodoList.query.filter_by(
        id=list_id,
        user_id=current_user_id
    ).first_or_404()
    
    # Get todos in this list
    todos = Todo.query.filter_by(
        list_id=list_id,
        user_id=current_user_id,
        parent_todo_id=None
    ).order_by(Todo.position, Todo.created_at).all()
    
    # Get statistics
    stats = {
        'total_todos': len(todos),
        'completed_todos': sum(1 for t in todos if t.completed),
        'pending_todos': sum(1 for t in todos if not t.completed),
        'high_priority': sum(1 for t in todos if t.priority == 'high' and not t.completed),
        'overdue': sum(1 for t in todos if t.due_date and t.due_date < datetime.utcnow() and not t.completed)
    }
    
    return jsonify({
        'list': todo_list.to_dict(),
        'todos': [todo.to_dict(include_subtasks=True) for todo in todos],
        'stats': stats
    }), 200

@lists_bp.route('/<int:list_id>', methods=['PUT'])
@jwt_required()
def update_list(list_id):
    """Update a todo list"""
    current_user_id = get_jwt_identity()
    
    todo_list = TodoList.query.filter_by(
        id=list_id,
        user_id=current_user_id
    ).first_or_404()
    
    data = request.get_json()
    changes = []
    
    if 'name' in data and data['name'] != todo_list.name:
        # Check for duplicate name
        duplicate = TodoList.query.filter_by(
            user_id=current_user_id,
            name=data['name'],
            is_archived=False
        ).first()
        if duplicate and duplicate.id != list_id:
            return jsonify({'error': 'A list with this name already exists'}), 409
        
        changes.append(f"name: '{todo_list.name}' -> '{data['name']}'")
        todo_list.name = data['name']
    
    if 'color' in data and data['color'] != todo_list.color:
        changes.append(f"color: {todo_list.color} -> {data['color']}")
        todo_list.color = data['color']
    
    if 'icon' in data and data['icon'] != todo_list.icon:
        changes.append(f"icon: {todo_list.icon} -> {data['icon']}")
        todo_list.icon = data['icon']
    
    if 'sort_order' in data and data['sort_order'] != todo_list.sort_order:
        changes.append(f"sort_order: {todo_list.sort_order} -> {data['sort_order']}")
        todo_list.sort_order = data['sort_order']
    
    db.session.commit()
    
    if changes:
        log_list_activity(current_user_id, 'UPDATE', list_id, 
                         f"Updated: {'; '.join(changes)}", request)
    
    return jsonify({
        'message': 'List updated successfully',
        'list': todo_list.to_dict(),
        'changes': changes
    }), 200

@lists_bp.route('/<int:list_id>', methods=['DELETE'])
@jwt_required()
def delete_list(list_id):
    """Delete a todo list (moves todos to default list)"""
    current_user_id = get_jwt_identity()
    
    todo_list = TodoList.query.filter_by(
        id=list_id,
        user_id=current_user_id
    ).first_or_404()
    
    if todo_list.is_default:
        return jsonify({'error': 'Cannot delete the default list'}), 400
    
    # Find or create default list
    default_list = TodoList.query.filter_by(
        user_id=current_user_id,
        is_default=True
    ).first()
    
    if not default_list:
        default_list = TodoList(
            name='My Tasks',
            is_default=True,
            user_id=current_user_id,
            sort_order=0
        )
        db.session.add(default_list)
        db.session.commit()
    
    # Move todos to default list
    Todo.query.filter_by(list_id=list_id).update({'list_id': default_list.id})
    
    # Log before deletion
    log_list_activity(current_user_id, 'DELETE', list_id, 
                     f"Deleted list: {todo_list.name}, moved todos to '{default_list.name}'", request)
    
    db.session.delete(todo_list)
    db.session.commit()
    
    return jsonify({
        'message': 'List deleted successfully',
        'moved_to_default': True,
        'default_list_id': default_list.id
    }), 200

@lists_bp.route('/<int:list_id>/archive', methods=['POST'])
@jwt_required()
def archive_list(list_id):
    """Archive a todo list"""
    current_user_id = get_jwt_identity()
    
    todo_list = TodoList.query.filter_by(
        id=list_id,
        user_id=current_user_id
    ).first_or_404()
    
    if todo_list.is_default:
        return jsonify({'error': 'Cannot archive the default list'}), 400
    
    todo_list.is_archived = True
    db.session.commit()
    
    log_list_activity(current_user_id, 'ARCHIVE', list_id, 
                     f"Archived list: {todo_list.name}", request)
    
    return jsonify({
        'message': 'List archived successfully',
        'list': todo_list.to_dict()
    }), 200

@lists_bp.route('/<int:list_id>/unarchive', methods=['POST'])
@jwt_required()
def unarchive_list(list_id):
    """Unarchive a todo list"""
    current_user_id = get_jwt_identity()
    
    todo_list = TodoList.query.filter_by(
        id=list_id,
        user_id=current_user_id
    ).first_or_404()
    
    todo_list.is_archived = False
    db.session.commit()
    
    log_list_activity(current_user_id, 'UNARCHIVE', list_id, 
                     f"Unarchived list: {todo_list.name}", request)
    
    return jsonify({
        'message': 'List unarchived successfully',
        'list': todo_list.to_dict()
    }), 200

@lists_bp.route('/reorder', methods=['POST'])
@jwt_required()
def reorder_lists():
    """Reorder lists"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('list_order') or not isinstance(data['list_order'], list):
        return jsonify({'error': 'list_order array is required'}), 400
    
    # Update sort_order for each list
    for idx, list_id in enumerate(data['list_order']):
        todo_list = TodoList.query.filter_by(
            id=list_id,
            user_id=current_user_id
        ).first()
        if todo_list:
            todo_list.sort_order = idx
    
    db.session.commit()
    
    log_list_activity(current_user_id, 'REORDER', None, 
                     f"Reordered {len(data['list_order'])} lists", request)
    
    return jsonify({
        'message': 'Lists reordered successfully',
        'count': len(data['list_order'])
    }), 200

@lists_bp.route('/default', methods=['GET'])
@jwt_required()
def get_default_list():
    """Get or create default list"""
    current_user_id = get_jwt_identity()
    
    default_list = TodoList.query.filter_by(
        user_id=current_user_id,
        is_default=True
    ).first()
    
    if not default_list:
        default_list = TodoList(
            name='My Tasks',
            is_default=True,
            user_id=current_user_id,
            sort_order=0
        )
        db.session.add(default_list)
        db.session.commit()
    
    return jsonify({
        'default_list': default_list.to_dict()
    }), 200

@lists_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_lists_stats():
    """Get statistics for all lists"""
    current_user_id = get_jwt_identity()
    
    lists = TodoList.query.filter_by(
        user_id=current_user_id,
        is_archived=False
    ).all()
    
    stats = []
    for todo_list in lists:
        total = todo_list.todos.count()
        completed = todo_list.todos.filter_by(completed=True).count()
        pending = total - completed
        
        stats.append({
            'list_id': todo_list.id,
            'name': todo_list.name,
            'color': todo_list.color,
            'total_todos': total,
            'completed_todos': completed,
            'pending_todos': pending,
            'completion_rate': round((completed / total * 100) if total > 0 else 0, 2)
        })
    
    return jsonify(stats), 200