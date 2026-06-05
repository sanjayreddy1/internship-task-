from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, ChatSession, ChatMessage, Todo, TodoList, ActivityLog
from utils.knowledge_base import generate_response, handle_task_action
from utils.export import generate_pdf, generate_docx, HAS_FPDF, HAS_DOCX
from datetime import datetime
import json
import logging
import io

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')
logger = logging.getLogger(__name__)


@chatbot_bp.route('/sessions', methods=['GET'])
@jwt_required()
def get_sessions():
    current_user_id = get_jwt_identity()
    sessions = ChatSession.query.filter_by(user_id=current_user_id)\
        .order_by(ChatSession.updated_at.desc()).all()
    return jsonify({
        'sessions': [s.to_dict() for s in sessions]
    }), 200


@chatbot_bp.route('/sessions', methods=['POST'])
@jwt_required()
def create_session():
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}

    session = ChatSession(
        user_id=current_user_id,
        title=str(data.get('title', 'New Chat'))
    )
    db.session.add(session)
    db.session.commit()

    welcome_msg = ChatMessage(
        session_id=session.id,
        role='assistant',
        content="Hello! I'm your Todo App assistant. Ask me anything about managing your tasks, "
                "using app features, or understanding your productivity stats!"
    )
    db.session.add(welcome_msg)
    db.session.commit()

    return jsonify({
        'message': 'Chat session created',
        'session': session.to_dict(),
        'welcome_message': welcome_msg.to_dict()
    }), 201


@chatbot_bp.route('/sessions/<int:session_id>', methods=['GET'])
@jwt_required()
def get_session(session_id):
    current_user_id = get_jwt_identity()
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user_id).first()
    if not session:
        return jsonify({'error': 'Chat session not found'}), 404

    messages = session.messages.order_by(ChatMessage.created_at.asc()).all()
    return jsonify({
        'session': session.to_dict(),
        'messages': [m.to_dict() for m in messages]
    }), 200


@chatbot_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@jwt_required()
def delete_session(session_id):
    current_user_id = get_jwt_identity()
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user_id).first()
    if not session:
        return jsonify({'error': 'Chat session not found'}), 404

    db.session.delete(session)
    db.session.commit()

    return jsonify({'message': 'Chat session deleted'}), 200


@chatbot_bp.route('/sessions/<int:session_id>/messages', methods=['POST'])
@jwt_required()
def send_message(session_id):
    current_user_id = get_jwt_identity()
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user_id).first()
    if not session:
        return jsonify({'error': 'Chat session not found'}), 404

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'error': 'Message content is required'}), 400

    raw_content = str(data['content']) if not isinstance(data['content'], str) else data['content']
    data['content'] = raw_content

    user_msg = ChatMessage(
        session_id=session_id,
        role='user',
        content=data['content']
    )
    db.session.add(user_msg)
    db.session.commit()

    history = session.messages.order_by(ChatMessage.created_at.asc()).all()
    conversation_history = [{"role": m.role, "content": m.content} for m in history]

    # Try action handling first
    action_result = handle_task_action(data['content'], conversation_history, current_user_id)

    if action_result and action_result.get('action'):
        action = action_result['action']
        action_type = action.get('type')
        bot_answer = action_result.get('answer', '')
        bot_sources = []

        if action_type == 'execute_create':
            task_data = action.get('data', {})
            title = task_data.get('title', 'Untitled')
            description = task_data.get('description', '')
            due_date_str = task_data.get('due_date')
            list_name = task_data.get('list_name')
            priority = task_data.get('priority', 'medium')

            due_date = None
            date_invalid = False
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str).replace(tzinfo=None)
                    if due_date < datetime.utcnow():
                        bot_answer = "Sorry, the due date is in the past. Task not created."
                        date_invalid = True
                except:
                    due_date_str = None

            if date_invalid:
                pass
            else:
                existing = Todo.query.filter_by(
                    user_id=current_user_id,
                    title=title,
                    completed=False,
                    status='pending'
                ).first()
                if existing:
                    bot_answer = f"A task with title '{title}' already exists. Task not created."
                else:
                    todo_list = None
                    if list_name:
                        todo_list = TodoList.query.filter_by(
                            user_id=current_user_id,
                            name=list_name,
                            is_archived=False
                        ).first()

                    if not todo_list:
                        todo_list = TodoList.query.filter_by(
                            user_id=current_user_id,
                            is_default=True
                        ).first()

                    list_id = todo_list.id if todo_list else None

                    from models import Todo
                    todo = Todo(
                        title=title,
                        description=description,
                        due_date=due_date,
                        list_id=list_id,
                        user_id=current_user_id,
                        priority=priority
                    )
                    db.session.add(todo)
                    db.session.commit()

                    due_text = f" due {due_date_str}" if due_date_str else ""
                    list_text = f" in '{todo_list.name}'" if todo_list else ""
                    priority_text = f" [{priority} priority]"
                    bot_answer = f"Task created! '{title}'{due_text}{list_text}{priority_text}."

        elif action_type == 'list_tasks':
            from models import Todo
            tasks = Todo.query.filter_by(
                user_id=current_user_id,
                completed=False,
                parent_todo_id=None
            ).order_by(Todo.created_at.desc()).limit(10).all()

            if not tasks:
                bot_answer = "You have no active tasks."
            else:
                task_lines = [f"{t.id}. {t.title}" + (f" [Due: {t.due_date.strftime('%b %d')}]" if t.due_date else "") for t in tasks]
                bot_answer = "Here are your active tasks:\n" + "\n".join(task_lines)

        elif action_type in ('complete_flow', 'delete_flow'):
            step = action.get('step')
            q = action.get('query')

            if step == 'lookup_complete':
                task = _find_task(q, current_user_id)
                if task:
                    if task.completed:
                        bot_answer = f"Task '{task.title}' is already completed."
                    else:
                        bot_answer = f"Task '{task.title}' found. Confirm complete: are you sure you want to mark it as complete? (Y/yes/complete)"
                else:
                    bot_answer = f"Task '{q}' does not exist. Please tell me another name or ID of the task to mark complete."

            elif step == 'lookup_delete':
                task = _find_task(q, current_user_id)
                if task:
                    bot_answer = f"Task '{task.title}' found. Confirm delete: are you sure you want to delete it? (Y/yes/delete)"
                else:
                    bot_answer = f"Task '{q}' does not exist. Please tell me another name or ID of the task to delete."

            elif step in ('execute_complete', 'execute_delete') and q:
                task = _find_task(q, current_user_id)

                if task:
                    if step == 'execute_complete':
                        if task.completed:
                            bot_answer = f"Task '{task.title}' was already completed."
                        else:
                            task.completed = True
                            task.completed_at = datetime.utcnow()
                            task.status = 'completed'
                            db.session.commit()
                            bot_answer = f"Task '{task.title}' marked as complete!"
                    else:
                        task.status = 'archived'
                        db.session.commit()
                        bot_answer = f"Task '{task.title}' has been deleted."
                else:
                    bot_answer = f"Could not find a task matching '{q}'. Please check the task ID or title."

        session.title = str(data['content'])[:100]

        bot_msg = ChatMessage(
            session_id=session_id,
            role='assistant',
            content=bot_answer,
            sources=None
        )
        db.session.add(bot_msg)
        db.session.commit()

        return jsonify({
            'user_message': user_msg.to_dict(),
            'bot_message': bot_msg.to_dict(),
            'sources': []
        }), 201

    # Fall back to RAG knowledge base
    try:
        result = generate_response(data['content'], conversation_history)
    except Exception as e:
        logger.error(f"Chatbot generate_response error: {str(e)}")
        result = {
            "answer": "I encountered an error processing your request. Please try again.",
            "sources": []
        }
    
    bot_answer = str(result.get('answer', ''))
    bot_sources = result.get('sources', [])
    if not isinstance(bot_sources, list):
        bot_sources = []

    bot_msg = ChatMessage(
        session_id=session_id,
        role='assistant',
        content=bot_answer,
        sources=json.dumps(bot_sources) if bot_sources else None
    )
    db.session.add(bot_msg)

    session.title = str(data['content'])[:100]
    db.session.commit()

    return jsonify({
        'user_message': user_msg.to_dict(),
        'bot_message': bot_msg.to_dict(),
        'sources': result['sources']
    }), 201


@chatbot_bp.route('/export/tasks/pdf', methods=['GET'])
@jwt_required()
def export_tasks_pdf():
    if not HAS_FPDF:
        return jsonify({'error': 'PDF export requires fpdf2. Install with: pip install fpdf2'}), 500

    current_user_id = get_jwt_identity()
    from models import User
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    todos = Todo.query.filter_by(user_id=current_user_id)\
        .order_by(Todo.created_at.desc()).all()

    todos_data = [t.to_dict(include_subtasks=True) for t in todos]

    try:
        pdf_bytes = generate_pdf(todos_data, username=user.username or user.email)

        _log_activity(current_user_id, 'EXPORT_PDF', 'export',
                      details=f'Exported {len(todos)} tasks as PDF')

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'tasks_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500


@chatbot_bp.route('/export/tasks/docx', methods=['GET'])
@jwt_required()
def export_tasks_docx():
    if not HAS_DOCX:
        return jsonify({'error': 'DOCX export requires python-docx. Install with: pip install python-docx'}), 500

    current_user_id = get_jwt_identity()
    from models import User
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    todos = Todo.query.filter_by(user_id=current_user_id)\
        .order_by(Todo.created_at.desc()).all()

    todos_data = [t.to_dict(include_subtasks=True) for t in todos]

    try:
        docx_bytes = generate_docx(todos_data, username=user.username or user.email)

        _log_activity(current_user_id, 'EXPORT_DOCX', 'export',
                      details=f'Exported {len(todos)} tasks as DOCX')

        return send_file(
            io.BytesIO(docx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f'tasks_{datetime.utcnow().strftime("%Y%m%d")}.docx'
        )
    except Exception as e:
        logger.error(f"DOCX export error: {str(e)}")
        return jsonify({'error': f'Failed to generate DOCX: {str(e)}'}), 500


def _find_task(q, user_id):
    from models import Todo
    task = None
    if q.isdigit():
        task = Todo.query.filter_by(id=int(q), user_id=user_id).first()
    if not task:
        results = Todo.query.filter(
            Todo.user_id == user_id,
            Todo.title.ilike(f'%{q}%'),
            Todo.parent_todo_id == None
        ).all()
        task = results[0] if results else None
    return task


def _log_activity(user_id, action, entity_type, entity_id=None, details=None):
    try:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")
        db.session.rollback()
