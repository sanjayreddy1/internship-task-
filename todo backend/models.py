from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import Bcrypt
from sqlalchemy import text, Index
import json

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_username', 'username'),
        Index('idx_users_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100))
    avatar_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    preferences = db.Column(db.Text, nullable=True)

    todos = db.relationship('Todo', backref='author', lazy='dynamic',
                            cascade='all, delete-orphan', foreign_keys='Todo.user_id')
    lists = db.relationship('TodoList', backref='owner', lazy='dynamic',
                            cascade='all, delete-orphan')
    labels = db.relationship('TodoLabel', backref='user', lazy='dynamic',
                             cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

    def get_preferences(self):
        if self.preferences:
            return json.loads(self.preferences)
        return {}

    def set_preferences(self, prefs):
        self.preferences = json.dumps(prefs)
        db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'preferences': self.get_preferences()
        }


class TodoList(db.Model):
    __tablename__ = 'todo_lists'
    __table_args__ = (
        Index('idx_lists_user', 'user_id'),
        Index('idx_lists_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#6366f1')
    icon = db.Column(db.String(50), default='list')
    is_default = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    todos = db.relationship('Todo', backref='list', lazy='dynamic',
                            cascade='all, delete-orphan', foreign_keys='Todo.list_id')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'icon': self.icon,
            'is_default': self.is_default,
            'is_archived': self.is_archived,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'todo_count': self.todos.filter_by(completed=False).count(),
            'total_todos': self.todos.count(),
            'completed_todos': self.todos.filter_by(completed=True).count()
        }


class Todo(db.Model):
    __tablename__ = 'todos'
    __table_args__ = (
        Index('idx_todos_user', 'user_id'),
        Index('idx_todos_list', 'list_id'),
        Index('idx_todos_completed', 'completed'),
        Index('idx_todos_due_date', 'due_date'),
        Index('idx_todos_priority', 'priority'),
        Index('idx_todos_status', 'status'),
        Index('idx_todos_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='pending')

    due_date = db.Column(db.DateTime, nullable=True)
    reminder_date = db.Column(db.DateTime, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)

    position = db.Column(db.Integer, default=0)

    is_recurring = db.Column(db.Boolean, default=False)
    recurring_pattern = db.Column(db.String(50), nullable=True)
    recurring_data = db.Column(db.Text, nullable=True)

    json_metadata = db.Column(db.Text, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    list_id = db.Column(db.Integer, db.ForeignKey('todo_lists.id', ondelete='SET NULL'), nullable=True)
    parent_todo_id = db.Column(db.Integer, db.ForeignKey('todos.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    subtasks = db.relationship('Todo', backref=db.backref('parent', remote_side=[id]),
                                lazy='dynamic', cascade='all, delete-orphan',
                                foreign_keys=[parent_todo_id])
    labels = db.relationship('TodoLabel', secondary='todo_label_association',
                             backref='todos', lazy='dynamic')
    attachments = db.relationship('TodoAttachment', backref='todo', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def get_metadata(self):
        if self.json_metadata:
            return json.loads(self.json_metadata)
        return {}

    def set_metadata(self, meta):
        self.json_metadata = json.dumps(meta)

    def get_recurring_data(self):
        if self.recurring_data:
            return json.loads(self.recurring_data)
        return {}

    def complete(self):
        self.completed = True
        self.completed_at = datetime.utcnow()
        self.status = 'completed'

    def reopen(self):
        self.completed = False
        self.completed_at = None
        self.status = 'pending'

    def to_dict(self, include_subtasks=False, include_labels=False, include_attachments=False):
        result = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'reminder_date': self.reminder_date.isoformat() if self.reminder_date else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'position': self.position,
            'list_id': self.list_id,
            'is_recurring': self.is_recurring,
            'recurring_pattern': self.recurring_pattern,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.get_metadata()
        }

        if include_subtasks:
            result['subtasks'] = [subtask.to_dict() for subtask in self.subtasks]
            result['subtask_count'] = self.subtasks.count()

        if include_labels:
            result['labels'] = [label.to_dict() for label in self.labels]

        if include_attachments:
            result['attachments'] = [attachment.to_dict() for attachment in self.attachments]

        return result


class TodoLabel(db.Model):
    __tablename__ = 'todo_labels'
    __table_args__ = (
        Index('idx_labels_user', 'user_id'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), default='#6366f1')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TodoLabelAssociation(db.Model):
    __tablename__ = 'todo_label_association'
    __table_args__ = (
        Index('idx_association_todo', 'todo_id'),
        Index('idx_association_label', 'label_id'),
    )

    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id', ondelete='CASCADE'), primary_key=True)
    label_id = db.Column(db.Integer, db.ForeignKey('todo_labels.id', ondelete='CASCADE'), primary_key=True)


class TodoAttachment(db.Model):
    __tablename__ = 'todo_attachments'
    __table_args__ = (
        Index('idx_attachments_todo', 'todo_id'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(100))
    todo_id = db.Column(db.Integer, db.ForeignKey('todos.id', ondelete='CASCADE'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    __table_args__ = (
        Index('idx_chat_sessions_user', 'user_id'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(100), default='New Chat')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic',
                                cascade='all, delete-orphan',
                                order_by='ChatMessage.created_at')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': self.messages.count()
        }


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        Index('idx_chat_messages_session', 'session_id'),
        Index('idx_chat_messages_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sources = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'sources': json.loads(self.sources) if self.sources else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    __table_args__ = (
        Index('idx_activity_user', 'user_id', 'created_at'),
        Index('idx_activity_action', 'action', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='activities')

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
