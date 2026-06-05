-- Create Database
CREATE DATABASE TodoDB;
GO

USE TodoDB;
GO

-- Enable SQL Server 2022 features
ALTER DATABASE TodoDB SET QUERY_STORE = ON;
ALTER DATABASE TodoDB SET ACCELERATED_PLAN_FORCING = ON;
GO

-- Create Schema
CREATE SCHEMA todo;
GO

-- Users Table with SQL Server 2022 specific features
CREATE TABLE todo.users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    email NVARCHAR(120) NOT NULL UNIQUE,
    username NVARCHAR(80) NOT NULL UNIQUE,
    password_hash NVARCHAR(128) NOT NULL,
    full_name NVARCHAR(100) NULL,
    avatar_url NVARCHAR(500) NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    last_login DATETIME2 NULL,
    
    -- JSON support for user preferences (SQL Server 2022 feature)
    preferences NVARCHAR(MAX) NULL,
    
    -- Indexes
    INDEX idx_users_email (email),
    INDEX idx_users_username (username),
    INDEX idx_users_created (created_at)
);
GO

-- Todo Lists Table
CREATE TABLE todo.todo_lists (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    color CHAR(7) DEFAULT '#6366f1',
    icon NVARCHAR(50) DEFAULT 'list',
    is_default BIT DEFAULT 0,
    is_archived BIT DEFAULT 0,
    user_id INT NOT NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    
    -- Ordering support
    sort_order INT DEFAULT 0,
    
    -- Foreign Key
    FOREIGN KEY (user_id) REFERENCES todo.users(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_lists_user (user_id),
    INDEX idx_lists_created (created_at)
);
GO

-- Todos Table with SQL Server 2022 features
CREATE TABLE todo.todos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    title NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX) NULL,
    completed BIT DEFAULT 0,
    priority NVARCHAR(20) DEFAULT 'medium',
    status NVARCHAR(20) DEFAULT 'pending',
    
    -- Date fields with timezone support
    due_date DATETIME2 NULL,
    reminder_date DATETIME2 NULL,
    start_date DATETIME2 NULL,
    
    -- Ordering and hierarchy
    position INT DEFAULT 0,
    
    -- Recurring tasks
    is_recurring BIT DEFAULT 0,
    recurring_pattern NVARCHAR(50) NULL,
    recurring_data NVARCHAR(MAX) NULL, -- JSON for recurring details
    
    -- JSON for additional metadata (SQL Server 2022)
    metadata NVARCHAR(MAX) NULL,
    
    -- Foreign Keys
    user_id INT NOT NULL,
    list_id INT NULL,
    parent_todo_id INT NULL,
    
    -- Timestamps
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    completed_at DATETIME2 NULL,
    
    -- Constraints
    FOREIGN KEY (user_id) REFERENCES todo.users(id) ON DELETE CASCADE,
    FOREIGN KEY (list_id) REFERENCES todo.todo_lists(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_todo_id) REFERENCES todo.todos(id),
    
    -- Check constraints
    CONSTRAINT chk_priority CHECK (priority IN ('low', 'medium', 'high')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'in_progress', 'completed', 'archived')),
    
    -- Indexes for performance
    INDEX idx_todos_user (user_id),
    INDEX idx_todos_list (list_id),
    INDEX idx_todos_completed (completed),
    INDEX idx_todos_due_date (due_date),
    INDEX idx_todos_priority (priority),
    INDEX idx_todos_status (status),
    INDEX idx_todos_created (created_at)
);
GO

-- Create filtered indexes for SQL Server 2022
CREATE INDEX idx_todos_active ON todo.todos (user_id, due_date) 
WHERE completed = 0;
GO

-- Labels Table
CREATE TABLE todo.todo_labels (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(50) NOT NULL,
    color CHAR(7) DEFAULT '#6366f1',
    user_id INT NOT NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (user_id) REFERENCES todo.users(id) ON DELETE CASCADE,
    
    INDEX idx_labels_user (user_id)
);
GO

-- Todo-Label Association Table
CREATE TABLE todo.todo_label_association (
    todo_id INT NOT NULL,
    label_id INT NOT NULL,
    
    PRIMARY KEY (todo_id, label_id),
    FOREIGN KEY (todo_id) REFERENCES todo.todos(id) ON DELETE CASCADE,
    FOREIGN KEY (label_id) REFERENCES todo.todo_labels(id) ON DELETE CASCADE
);
GO

-- Attachments Table
CREATE TABLE todo.todo_attachments (
    id INT IDENTITY(1,1) PRIMARY KEY,
    filename NVARCHAR(255) NOT NULL,
    file_url NVARCHAR(500) NOT NULL,
    file_size INT NULL,
    file_type NVARCHAR(100) NULL,
    todo_id INT NOT NULL,
    uploaded_at DATETIME2 DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (todo_id) REFERENCES todo.todos(id) ON DELETE CASCADE,
    
    INDEX idx_attachments_todo (todo_id)
);
GO

-- Activity Log Table for Analytics (SQL Server 2022 temporal table)
CREATE TABLE todo.activity_log (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    action NVARCHAR(50) NOT NULL,
    entity_type NVARCHAR(50) NOT NULL,
    entity_id INT NULL,
    details NVARCHAR(MAX) NULL,
    ip_address NVARCHAR(45) NULL,
    user_agent NVARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (user_id) REFERENCES todo.users(id) ON DELETE CASCADE,
    
    INDEX idx_activity_user (user_id, created_at),
    INDEX idx_activity_action (action, created_at)
);
GO

-- Create a temporal table for todo history (SQL Server 2022 feature)
CREATE TABLE todo.todos_history (
    id INT NOT NULL,
    title NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX) NULL,
    completed BIT DEFAULT 0,
    priority NVARCHAR(20) DEFAULT 'medium',
    status NVARCHAR(20) DEFAULT 'pending',
    due_date DATETIME2 NULL,
    user_id INT NOT NULL,
    list_id INT NULL,
    valid_from DATETIME2 NOT NULL,
    valid_to DATETIME2 NOT NULL,
    
    INDEX idx_history_dates (valid_from, valid_to)
);
GO

-- Stored Procedures for Common Operations

-- Get user statistics
CREATE OR REPLACE PROCEDURE todo.sp_get_user_stats
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        COUNT(CASE WHEN completed = 0 THEN 1 END) AS pending_count,
        COUNT(CASE WHEN completed = 1 THEN 1 END) AS completed_count,
        COUNT(CASE WHEN due_date < GETUTCDATE() AND completed = 0 THEN 1 END) AS overdue_count,
        COUNT(CASE WHEN due_date IS NOT NULL AND completed = 0 THEN 1 END) AS with_due_date,
        COUNT(CASE WHEN priority = 'high' AND completed = 0 THEN 1 END) AS high_priority_count
    FROM todo.todos
    WHERE user_id = @user_id;
END;
GO

-- Function to get todo completion rate
CREATE FUNCTION todo.fn_get_completion_rate(@user_id INT)
RETURNS DECIMAL(5,2)
AS
BEGIN
    DECLARE @completion_rate DECIMAL(5,2);
    
    SELECT @completion_rate = 
        CASE 
            WHEN COUNT(*) > 0 THEN 
                (CAST(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS DECIMAL(10,2)) / COUNT(*) * 100)
            ELSE 0
        END
    FROM todo.todos
    WHERE user_id = @user_id;
    
    RETURN @completion_rate;
END;
GO

-- Trigger to update updated_at timestamp
CREATE TRIGGER todo.trg_update_timestamp
ON todo.todos
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE todo.todos
    SET updated_at = GETUTCDATE()
    FROM todo.todos t
    INNER JOIN inserted i ON t.id = i.id;
END;
GO

-- Trigger to log activities
CREATE TRIGGER todo.trg_log_todo_activity
ON todo.todos
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Log inserts
    INSERT INTO todo.activity_log (user_id, action, entity_type, entity_id, created_at)
    SELECT 
        i.user_id, 
        'CREATE', 
        'todo', 
        i.id,
        GETUTCDATE()
    FROM inserted i
    WHERE NOT EXISTS (SELECT 1 FROM deleted WHERE deleted.id = i.id);
    
    -- Log updates
    INSERT INTO todo.activity_log (user_id, action, entity_type, entity_id, details, created_at)
    SELECT 
        i.user_id, 
        'UPDATE', 
        'todo', 
        i.id,
        'Updated todo',
        GETUTCDATE()
    FROM inserted i
    INNER JOIN deleted d ON i.id = d.id;
    
    -- Log deletes
    INSERT INTO todo.activity_log (user_id, action, entity_type, entity_id, created_at)
    SELECT 
        d.user_id, 
        'DELETE', 
        'todo', 
        d.id,
        GETUTCDATE()
    FROM deleted d;
END;
GO

-- Create default data
INSERT INTO todo.todo_labels (name, color, user_id) VALUES
('Work', '#ef4444', 1),
('Personal', '#3b82f6', 1),
('Shopping', '#10b981', 1),
('Health', '#8b5cf6', 1),
('Learning', '#f59e0b', 1);
GO

-- Create views for reporting
CREATE VIEW todo.vw_daily_todo_stats AS
SELECT 
    CAST(created_at AS DATE) AS date,
    COUNT(*) AS total_created,
    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS total_completed,
    COUNT(DISTINCT user_id) AS active_users
FROM todo.todos
GROUP BY CAST(created_at AS DATE);
GO

-- Enable Query Store for performance monitoring
ALTER DATABASE TodoDB SET QUERY_STORE = ON;
ALTER DATABASE TodoDB SET QUERY_STORE (OPERATION_MODE = READ_WRITE);
GO