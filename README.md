# Todo App Backend

A feature-rich Flask REST API for task management with analytics, AI chatbot assistant, export capabilities, and SQL Server 2022 / SQLite support.

## Features

- **Task Management** — CRUD for todos with subtasks, labels, attachments, priorities, due dates, and recurring tasks
- **Lists** — Organize tasks into customizable lists with colors/icons, drag-and-drop reordering, archive/unarchive
- **Dashboard** — Real-time stats (overdue, due today/this week/month), weekly/monthly progress charts, priority breakdown
- **Analytics** — Completion trends, productivity scoring (4-factor model), peak hour analysis, label-based analysis, task completion forecasting
- **AI Chatbot** — Natural language task management (create/list/complete/delete tasks via chat) with a RAG knowledge base for app guidance
- **Export** — Task export as PDF or DOCX
- **Authentication** — JWT-based auth with register, login, token refresh, password change/reset, account deactivation
- **Activity Logging** — Full audit trail for all user actions
- **Batch Operations** — Bulk complete/delete/move/archive todos

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.x |
| Database | SQLite (dev) / SQL Server 2022 (prod) |
| ORM | SQLAlchemy |
| Auth | JWT (Flask-JWT-Extended) |
| Password | Flask-Bcrypt |
| CORS | Flask-CORS |
| PDF Export | fpdf2 |
| DOCX Export | python-docx |
| State | python-dotenv |

## Project Structure

```
├── app.py                 # Application factory & entry point
├── config.py              # Configuration (SQLite/MSSQL, JWT, CORS)
├── models.py              # SQLAlchemy models
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── init_db.sql            # MSSQL schema + procs + triggers
├── routes/
│   ├── auth.py            # Register, login, profile, password mgmt
│   ├── todos.py           # CRUD, subtasks, batch, recurring, cleanup
│   ├── lists.py           # CRUD, archive/unarchive, reorder, stats
│   ├── dashboard.py       # Summary, activity, charts, tips
│   ├── analytics.py       # Trends, productivity score, forecast
│   └── chatbot.py         # Chat sessions, messaging, PDF/DOCX export
├── utils/
│   ├── helpers.py         # Utility functions
│   ├── validators.py      # Input validation
│   ├── decoders.py        # Data decoders
│   ├── export.py          # PDF & DOCX generation
│   └── knowledge_base.py  # Chatbot RAG knowledge base
├── templates/
│   └── app.html           # Single-page frontend
├── uploads/               # File upload directory
└── instance/
    └── todo.db            # Default SQLite database
```

## Quick Start

### Prerequisites

- Python 3.10+
- SQL Server 2022 (optional — defaults to SQLite)

### Installation

```bash
# Clone and enter the project
cd todo-backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env .env.local
# Edit .env.local as needed

# Run
python app.py
```

The server starts at `http://localhost:5000`.

### Database Setup

**SQLite** (default) — no setup needed. The database file is created at `instance/todo.db` on first run.

**SQL Server 2022** — set `USE_SQLITE=false` in `.env`, configure your DB credentials, then run:

```bash
sqlcmd -S localhost -i init_db.sql
```

A default admin user is auto-created (`admin@example.com` / `Admin@123`).

## API Reference

All endpoints (`/api/*`) return JSON. Protected endpoints require a `Bearer` token in the `Authorization` header.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login (email or username) |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/profile` | Get current user profile |
| PUT | `/api/auth/profile` | Update profile |
| POST | `/api/auth/change-password` | Change password |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/reset-password-request` | Request password reset |
| POST | `/api/auth/reset-password` | Reset password with token |
| DELETE | `/api/auth/deactivate` | Deactivate account |

### Todos

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/todos/` | List todos (filters: list_id, status, priority, search, due_date range, pagination) |
| POST | `/api/todos/` | Create a todo |
| GET | `/api/todos/<id>` | Get todo with subtasks, labels, attachments, activity |
| PUT | `/api/todos/<id>` | Update a todo |
| PATCH | `/api/todos/<id>/complete` | Mark complete (auto-generates recurring) |
| PATCH | `/api/todos/<id>/reopen` | Reopen a completed todo |
| DELETE | `/api/todos/<id>` | Soft-delete (archive) |
| POST | `/api/todos/<id>/subtasks` | Add a subtask |
| PUT | `/api/todos/<id>/subtasks/<subtask_id>` | Update a subtask |
| POST | `/api/todos/batch` | Batch operations (delete/complete/reopen/move) |
| POST | `/api/todos/recurring/generate` | Generate next recurring instances |
| POST | `/api/todos/cleanup` | Archive completed todos older than 30 days |
| GET | `/api/todos/export` | Export active todos as JSON |

### Lists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lists/` | Get all lists (+ archived) |
| POST | `/api/lists/` | Create a list |
| GET | `/api/lists/<id>` | Get list with its todos |
| PUT | `/api/lists/<id>` | Update list |
| DELETE | `/api/lists/<id>` | Delete list (todos moved to default) |
| POST | `/api/lists/<id>/archive` | Archive list |
| POST | `/api/lists/<id>/unarchive` | Unarchive list |
| POST | `/api/lists/reorder` | Reorder lists |
| GET | `/api/lists/default` | Get/create default list |
| GET | `/api/lists/stats` | Per-list statistics |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Overall stats (overdue, due today/week/month) |
| GET | `/api/dashboard/recent-activity` | Recent user activity |
| GET | `/api/dashboard/priority-breakdown` | Todos grouped by priority |
| GET | `/api/dashboard/weekly-progress` | Last 7 days created/completed |
| GET | `/api/dashboard/monthly-progress` | Last 6 months created/completed |
| GET | `/api/dashboard/upcoming-todos` | Todos due in next 7 days |
| GET | `/api/dashboard/recent-completed` | Recently completed (last 7 days) |
| GET | `/api/dashboard/productivity-tips` | Personalized tips based on data |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/completion-trends` | Daily completion trends |
| GET | `/api/analytics/productivity-score` | Weighted productivity score (4 factors) |
| GET | `/api/analytics/peak-hours` | Peak productivity hour analysis |
| GET | `/api/analytics/labels-analysis` | Per-label completion stats |
| GET | `/api/analytics/forecast` | Next week completion prediction |
| GET | `/api/analytics/export-report` | Full analytics report as JSON |

### Chatbot

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chatbot/sessions` | List chat sessions |
| POST | `/api/chatbot/sessions` | Create new session |
| GET | `/api/chatbot/sessions/<id>` | Get session with messages |
| DELETE | `/api/chatbot/sessions/<id>` | Delete session |
| POST | `/api/chatbot/sessions/<id>/messages` | Send message (NL task mgmt + RAG) |
| GET | `/api/chatbot/export/tasks/pdf` | Export tasks as PDF |
| GET | `/api/chatbot/export/tasks/docx` | Export tasks as DOCX |

## Configuration

Key environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key-...` | Flask secret key |
| `JWT_SECRET_KEY` | `jwt-secret-key-...` | JWT signing key |
| `USE_SQLITE` | `true` | Use SQLite (vs SQL Server) |
| `DB_USER`/`DB_PASSWORD` | — | SQL Server credentials |
| `DB_HOST`/`DB_PORT` | `localhost:1433` | SQL Server host |
| `DB_NAME` | `TodoDB` | Database name |
| `DB_DRIVER` | `ODBC Driver 18 for SQL Server` | ODBC driver name |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5000` | Allowed origins |
| `UPLOAD_FOLDER` | `./uploads` | File upload directory |

## Password Policy

- Minimum 8 characters
- At least 1 uppercase, 1 lowercase, 1 digit, 1 special character


