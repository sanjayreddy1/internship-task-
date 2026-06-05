# routes/todos.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Todo, TodoList, TodoLabel, TodoAttachment, ActivityLog
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, text, func, case
import json
import logging

todos_bp = Blueprint('todos', __name__, url_prefix='/api/todos')
logger = logging.getLogger(__name__)

def log_todo_activity(user_id, action, todo_id, details=None, request_obj=None):
    """Log todo activity"""
    try:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type='todo',
            entity_id=todo_id,
            details=details,
            ip_address=request_obj.remote_addr if request_obj else None,
            user_agent=request_obj.user_agent.string if request_obj and hasattr(request_obj, 'user_agent') else None
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging todo activity: {str(e)}")
        db.session.rollback()

@todos_bp.route('/', methods=['GET'])
@jwt_required()
def get_todos():
    """Get all todos for current user with advanced filters"""
    current_user_id = get_jwt_identity()
    
    # Get query parameters
    list_id = request.args.get('list_id', type=int)
    status = request.args.get('status', 'active')
    days = request.args.get('days', type=int)
    priority = request.args.get('priority')
    label_id = request.args.get('label_id', type=int)
    search = request.args.get('search')
    completed_after = request.args.get('completed_after')
    completed_before = request.args.get('completed_before')
    due_date_from = request.args.get('due_date_from')
    due_date_to = request.args.get('due_date_to')
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort_by = request.args.get('sort_by', 'position')
    sort_order = request.args.get('sort_order', 'asc')
    
    # Base query
    query = Todo.query.filter_by(user_id=current_user_id, parent_todo_id=None)
    
    # Apply filters
    if list_id:
        query = query.filter_by(list_id=list_id)
    
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(
            or_(
                Todo.created_at >= cutoff,
                Todo.completed_at >= cutoff,
                Todo.due_date >= cutoff
            )
        )
    elif status == 'active':
        query = query.filter_by(completed=False, status='pending')
    elif status == 'completed':
        query = query.filter_by(completed=True)
    elif status == 'overdue':
        query = query.filter(
            Todo.completed == False,
            Todo.due_date < datetime.utcnow(),
            Todo.due_date.isnot(None)
        )
    elif status == 'today':
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        query = query.filter(
            Todo.due_date >= today_start,
            Todo.due_date < today_end,
            Todo.completed == False
        )
    elif status == 'all':
        query = query.filter(Todo.status != 'archived')
    elif status == 'upcoming':
        tomorrow = datetime.utcnow() + timedelta(days=1)
        next_week = datetime.utcnow() + timedelta(days=7)
        query = query.filter(
            Todo.due_date >= tomorrow,
            Todo.due_date <= next_week,
            Todo.completed == False
        )
    
    if priority:
        query = query.filter_by(priority=priority)
    
    if label_id:
        query = query.filter(Todo.labels.any(id=label_id))
    
    if search:
        query = query.filter(
            or_(
                Todo.title.ilike(f'%{search}%'),
                Todo.description.ilike(f'%{search}%')
            )
        )
    
    if due_date_from:
        due_date_from_dt = datetime.fromisoformat(due_date_from)
        query = query.filter(Todo.due_date >= due_date_from_dt)
    
    if due_date_to:
        due_date_to_dt = datetime.fromisoformat(due_date_to)
        query = query.filter(Todo.due_date <= due_date_to_dt)
    
    if completed_after:
        completed_after_dt = datetime.fromisoformat(completed_after)
        query = query.filter(Todo.completed_at >= completed_after_dt)
    
    if completed_before:
        completed_before_dt = datetime.fromisoformat(completed_before)
        query = query.filter(Todo.completed_at <= completed_before_dt)
    
    # Apply sorting
    if sort_by == 'due_date':
        order_column = Todo.due_date
    elif sort_by == 'priority':
        order_column = Todo.priority
    elif sort_by == 'created_at':
        order_column = Todo.created_at
    elif sort_by == 'updated_at':
        order_column = Todo.updated_at
    elif sort_by == 'title':
        order_column = Todo.title
    else:
        order_column = Todo.position
    
    if sort_order == 'desc':
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Pagination
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    from sqlalchemy import case
    stats_query = db.session.query(
        func.count(Todo.id).label('total'),
        func.sum(case((Todo.completed == True, 1), else_=0)).label('completed'),
        func.sum(case((Todo.priority == 'high', 1), else_=0)).label('high_priority')
    ).filter(Todo.user_id == current_user_id, Todo.parent_todo_id == None)
    
    stats = stats_query.first()
    
    return jsonify({
        'todos': [todo.to_dict(include_subtasks=True, include_labels=True) for todo in paginated.items],
        'pagination': {
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'pages': paginated.pages,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev
        },
        'stats': {
            'total_todos': stats.total or 0,
            'completed_todos': stats.completed or 0,
            'completion_rate': round((stats.completed or 0) / (stats.total or 1) * 100, 2),
            'high_priority_count': stats.high_priority or 0
        }
    }), 200

@todos_bp.route('/<int:todo_id>', methods=['GET'])
@jwt_required()
def get_todo(todo_id):
    """Get single todo by ID with full details"""
    current_user_id = get_jwt_identity()
    
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    
    # Get activity log for this todo
    activities = ActivityLog.query.filter_by(
        entity_type='todo',
        entity_id=todo_id
    ).order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    return jsonify({
        'todo': todo.to_dict(include_subtasks=True, include_labels=True, include_attachments=True),
        'activities': [act.to_dict() for act in activities]
    }), 200

@todos_bp.route('/', methods=['POST'])
@jwt_required()
def create_todo():
    """Create a new todo"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    raw_title = data.get('title')
    if raw_title is None or (isinstance(raw_title, str) and not raw_title.strip()):
        return jsonify({'error': 'Title is required'}), 400
    data['title'] = str(raw_title).strip()
    
    # Get list_id (use default list if not specified)
    list_id = data.get('list_id')
    if not list_id:
        default_list = TodoList.query.filter_by(
            user_id=current_user_id, 
            is_default=True
        ).first()
        if default_list:
            list_id = default_list.id
    
    # Parse dates
    def parse_date(date_str):
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                return None
        return None
    
    due_date = parse_date(data.get('due_date'))
    if due_date:
        due_date = due_date.replace(tzinfo=None)
        if due_date < datetime.utcnow():
            return jsonify({'error': 'Cannot assign a task to a past date'}), 400
    reminder_date = parse_date(data.get('reminder_date'))
    start_date = parse_date(data.get('start_date'))
    
    # Check for duplicate title in same list
    existing = Todo.query.filter_by(
        user_id=current_user_id,
        title=data['title'],
        list_id=list_id,
        completed=False,
        status='pending'
    ).first()
    if existing:
        return jsonify({'error': 'A task with this title already exists in this list'}), 409

    # Get max position for ordering
    max_position = db.session.query(func.max(Todo.position)).filter_by(
        user_id=current_user_id,
        list_id=list_id
    ).scalar() or 0
    
    # Create todo
    todo = Todo(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'medium'),
        due_date=due_date,
        reminder_date=reminder_date,
        start_date=start_date,
        list_id=list_id,
        user_id=current_user_id,
        is_recurring=data.get('is_recurring', False),
        recurring_pattern=data.get('recurring_pattern'),
        position=max_position + 1
    )
    
    # Set metadata if provided
    if data.get('metadata'):
        todo.set_metadata(data['metadata'])
    
    # Set recurring data if provided
    if data.get('recurring_data'):
        todo.recurring_data = json.dumps(data['recurring_data'])
    
    db.session.add(todo)
    db.session.commit()
    
    # Add labels if provided
    if data.get('label_ids'):
        labels = TodoLabel.query.filter(
            TodoLabel.id.in_(data['label_ids']),
            TodoLabel.user_id == current_user_id
        ).all()
        todo.labels = labels
        db.session.commit()
    
    # Log activity
    log_todo_activity(current_user_id, 'CREATE', todo.id, 
                     f"Created todo: {todo.title}", request)
    
    return jsonify({
        'message': 'Todo created successfully',
        'todo': todo.to_dict(include_labels=True)
    }), 201

@todos_bp.route('/<int:todo_id>', methods=['PUT'])
@jwt_required()
def update_todo(todo_id):
    """Update a todo"""
    current_user_id = get_jwt_identity()
    
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    data = request.get_json()
    
    changes = []
    
    # Update fields
    if 'title' in data:
        new_title = str(data['title']).strip() if data['title'] is not None else ''
        if new_title != todo.title:
            target_list_id = data.get('list_id', todo.list_id)
            existing = Todo.query.filter(
                Todo.user_id == current_user_id,
                Todo.title == new_title,
                Todo.list_id == target_list_id,
                Todo.completed == False,
                Todo.status == 'pending',
                Todo.id != todo_id
            ).first()
            if existing:
                return jsonify({'error': 'A task with this title already exists in this list'}), 409
            changes.append(f"title: '{todo.title}' -> '{new_title}'")
            todo.title = new_title
    
    if 'description' in data and data['description'] != todo.description:
        changes.append("description updated")
        todo.description = data['description']
    
    if 'priority' in data and data['priority'] != todo.priority:
        changes.append(f"priority: {todo.priority} -> {data['priority']}")
        todo.priority = data['priority']
    
    if 'status' in data and data['status'] != todo.status:
        changes.append(f"status: {todo.status} -> {data['status']}")
        todo.status = data['status']
    
    if 'list_id' in data and data['list_id'] != todo.list_id:
        changes.append(f"list_id: {todo.list_id} -> {data['list_id']}")
        todo.list_id = data['list_id']
    
    if 'position' in data and data['position'] != todo.position:
        changes.append(f"position: {todo.position} -> {data['position']}")
        todo.position = data['position']
    
    # Date updates
    def update_date_field(field_name, date_str):
        nonlocal changes
        new_date = None
        if date_str:
            try:
                new_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                pass
        old_date = getattr(todo, field_name)
        if new_date != old_date:
            changes.append(f"{field_name}: {old_date} -> {new_date}")
            setattr(todo, field_name, new_date)
    
    if 'due_date' in data:
        if data['due_date']:
            new_due = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')).replace(tzinfo=None)
            if new_due < datetime.utcnow():
                return jsonify({'error': 'Cannot assign a task to a past date'}), 400
        update_date_field('due_date', data['due_date'])
    
    if 'reminder_date' in data:
        update_date_field('reminder_date', data['reminder_date'])
    
    if 'start_date' in data:
        update_date_field('start_date', data['start_date'])
    
    # Recurring updates
    if 'is_recurring' in data:
        todo.is_recurring = data['is_recurring']
        changes.append(f"is_recurring: {data['is_recurring']}")
    
    if 'recurring_pattern' in data:
        todo.recurring_pattern = data['recurring_pattern']
        changes.append(f"recurring_pattern: {data['recurring_pattern']}")
    
    # Metadata update
    if data.get('metadata'):
        todo.set_metadata(data['metadata'])
        changes.append("metadata updated")
    
    db.session.commit()
    
    # Update labels if provided
    if 'label_ids' in data:
        labels = TodoLabel.query.filter(
            TodoLabel.id.in_(data['label_ids']),
            TodoLabel.user_id == current_user_id
        ).all()
        todo.labels = labels
        db.session.commit()
        changes.append(f"labels updated: {len(labels)} labels")
    
    # Log activity
    if changes:
        log_todo_activity(current_user_id, 'UPDATE', todo.id, 
                         f"Updated: {'; '.join(changes)}", request)
    
    return jsonify({
        'message': 'Todo updated successfully',
        'todo': todo.to_dict(include_labels=True),
        'changes': changes
    }), 200

@todos_bp.route('/<int:todo_id>/complete', methods=['PATCH'])
@jwt_required()
def complete_todo(todo_id):
    """Mark todo as complete"""
    current_user_id = get_jwt_identity()
    
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    
    if not todo.completed:
        todo.complete()
        db.session.commit()
        
        # Log completion
        log_todo_activity(current_user_id, 'COMPLETE', todo.id, 
                         f"Completed todo: {todo.title}", request)
        
        # Check if this is a recurring task and create next instance
        if todo.is_recurring and todo.recurring_pattern:
            create_next_recurring_todo(todo)
    
    return jsonify({
        'message': 'Todo completed',
        'todo': todo.to_dict(),
        'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
    }), 200

@todos_bp.route('/<int:todo_id>/reopen', methods=['PATCH'])
@jwt_required()
def reopen_todo(todo_id):
    """Reopen a completed todo"""
    current_user_id = get_jwt_identity()
    
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    
    if todo.completed:
        todo.reopen()
        db.session.commit()
        
        # Log reopening
        log_todo_activity(current_user_id, 'REOPEN', todo.id, 
                         f"Reopened todo: {todo.title}", request)
    
    return jsonify({
        'message': 'Todo reopened',
        'todo': todo.to_dict()
    }), 200

@todos_bp.route('/<int:todo_id>', methods=['DELETE'])
@jwt_required()
def delete_todo(todo_id):
    """Delete a todo (soft delete by archiving)"""
    current_user_id = get_jwt_identity()
    
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    
    # Soft delete - change status to archived
    todo.status = 'archived'
    db.session.commit()
    
    # Log deletion
    log_todo_activity(current_user_id, 'DELETE', todo.id, 
                     f"Deleted todo: {todo.title}", request)
    
    return jsonify({'message': 'Todo deleted successfully'}), 200

@todos_bp.route('/<int:todo_id>/subtasks', methods=['POST'])
@jwt_required()
def add_subtask(todo_id):
    """Add a subtask to a todo"""
    current_user_id = get_jwt_identity()
    
    parent_todo = Todo.query.filter_by(id=todo_id, user_id=current_user_id).first_or_404()
    data = request.get_json()
    
    if not data.get('title'):
        return jsonify({'error': 'Subtask title is required'}), 400
    
    subtask = Todo(
        title=data['title'],
        description=data.get('description', ''),
        user_id=current_user_id,
        parent_todo_id=todo_id,
        priority='low'  # Subtasks default to low priority
    )
    
    db.session.add(subtask)
    db.session.commit()
    
    # Log activity
    log_todo_activity(current_user_id, 'ADD_SUBTASK', subtask.id, 
                     f"Added subtask to '{parent_todo.title}': {subtask.title}", request)
    
    return jsonify({
        'message': 'Subtask added',
        'subtask': subtask.to_dict()
    }), 201

@todos_bp.route('/<int:todo_id>/subtasks/<int:subtask_id>', methods=['PUT'])
@jwt_required()
def update_subtask(todo_id, subtask_id):
    """Update a subtask"""
    current_user_id = get_jwt_identity()
    
    subtask = Todo.query.filter_by(
        id=subtask_id, 
        user_id=current_user_id,
        parent_todo_id=todo_id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'title' in data:
        subtask.title = data['title']
    if 'description' in data:
        subtask.description = data['description']
    if 'completed' in data:
        if data['completed'] and not subtask.completed:
            subtask.complete()
        elif not data['completed'] and subtask.completed:
            subtask.reopen()
    
    db.session.commit()
    
    log_todo_activity(current_user_id, 'UPDATE_SUBTASK', subtask.id, 
                     f"Updated subtask: {subtask.title}", request)
    
    return jsonify({
        'message': 'Subtask updated',
        'subtask': subtask.to_dict()
    }), 200

@todos_bp.route('/batch', methods=['POST'])
@jwt_required()
def batch_operation():
    """Perform batch operations on multiple todos"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    todo_ids = data.get('todo_ids', [])
    operation = data.get('operation')
    
    if not todo_ids or not operation:
        return jsonify({'error': 'Todo IDs and operation are required'}), 400
    
    todos = Todo.query.filter(
        Todo.id.in_(todo_ids),
        Todo.user_id == current_user_id
    ).all()
    
    if not todos:
        return jsonify({'error': 'No valid todos found'}), 404
    
    operation_map = {
        'delete': lambda t: setattr(t, 'status', 'archived'),
        'complete': lambda t: t.complete(),
        'reopen': lambda t: t.reopen(),
        'archive': lambda t: setattr(t, 'status', 'archived')
    }
    
    if operation not in operation_map:
        return jsonify({'error': 'Invalid operation'}), 400
    
    # Apply operation
    for todo in todos:
        operation_map[operation](todo)
    
    # Handle move operation separately
    if operation == 'move':
        new_list_id = data.get('list_id')
        if not new_list_id:
            return jsonify({'error': 'List ID required for move operation'}), 400
        for todo in todos:
            todo.list_id = new_list_id
        message = f'{len(todos)} todos moved'
    elif operation == 'delete':
        message = f'{len(todos)} todos deleted'
    elif operation == 'complete':
        message = f'{len(todos)} todos completed'
    elif operation == 'reopen':
        message = f'{len(todos)} todos reopened'
    else:
        message = f'{operation} operation completed on {len(todos)} todos'
    
    db.session.commit()
    
    # Log batch operation
    log_todo_activity(current_user_id, f'BATCH_{operation.upper()}', None, 
                     f"Batch {operation} on {len(todos)} todos: {todo_ids}", request)
    
    return jsonify({
        'message': message,
        'affected_count': len(todos),
        'operation': operation
    }), 200

@todos_bp.route('/recurring/generate', methods=['POST'])
@jwt_required()
def generate_recurring_todos():
    """Generate recurring todos for the next period"""
    current_user_id = get_jwt_identity()
    
    recurring_todos = Todo.query.filter_by(
        user_id=current_user_id,
        is_recurring=True,
        completed=True
    ).all()
    
    generated_count = 0
    for todo in recurring_todos:
        if create_next_recurring_todo(todo):
            generated_count += 1
    
    return jsonify({
        'message': f'Generated {generated_count} recurring todos',
        'count': generated_count
    }), 200

def create_next_recurring_todo(completed_todo):
    """Create next instance of a recurring todo"""
    try:
        recurring_data = completed_todo.get_recurring_data()
        next_due_date = None
        
        if completed_todo.recurring_pattern == 'daily':
            next_due_date = (completed_todo.due_date or datetime.utcnow()) + timedelta(days=1)
        elif completed_todo.recurring_pattern == 'weekly':
            next_due_date = (completed_todo.due_date or datetime.utcnow()) + timedelta(weeks=1)
        elif completed_todo.recurring_pattern == 'monthly':
            # Add month - simplified
            next_due_date = (completed_todo.due_date or datetime.utcnow()) + timedelta(days=30)
        
        if next_due_date:
            new_todo = Todo(
                title=completed_todo.title,
                description=completed_todo.description,
                priority=completed_todo.priority,
                due_date=next_due_date,
                list_id=completed_todo.list_id,
                user_id=completed_todo.user_id,
                is_recurring=True,
                recurring_pattern=completed_todo.recurring_pattern,
                recurring_data=completed_todo.recurring_data
            )
            db.session.add(new_todo)
            db.session.commit()
            return True
    except Exception as e:
        logger.error(f"Error creating recurring todo: {str(e)}")
        db.session.rollback()
    
    return False

@todos_bp.route('/cleanup', methods=['POST'])
@jwt_required()
def cleanup_old_todos():
    """Archive todos older than 30 days"""
    current_user_id = get_jwt_identity()
    cutoff = datetime.utcnow() - timedelta(days=30)

    old_todos = Todo.query.filter(
        Todo.user_id == current_user_id,
        Todo.completed == True,
        Todo.completed_at < cutoff
    ).all()

    count = 0
    for todo in old_todos:
        todo.status = 'archived'
        count += 1

    if count:
        db.session.commit()

    return jsonify({
        'message': f'Archived {count} old completed todos',
        'count': count
    }), 200

@todos_bp.route('/export', methods=['GET'])
@jwt_required()
def export_todos():
    """Export todos to JSON format"""
    current_user_id = get_jwt_identity()
    
    # Get all todos for user (not completed, not archived)
    todos = Todo.query.filter_by(
        user_id=current_user_id,
        status='pending'
    ).order_by(Todo.created_at).all()
    
    export_data = {
        'export_date': datetime.utcnow().isoformat(),
        'user_id': current_user_id,
        'total_count': len(todos),
        'todos': [todo.to_dict(include_subtasks=True, include_labels=True) for todo in todos]
    }
    
    log_todo_activity(current_user_id, 'EXPORT', None, 
                     f"Exported {len(todos)} todos", request)
    
    return jsonify(export_data), 200