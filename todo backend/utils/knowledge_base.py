import re
import math
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Optional

KNOWLEDGE_BASE = [
    {
        "id": "intro",
        "category": "general",
        "title": "What is this Todo App?",
        "keywords": ["what is", "about", "introduction", "overview", "purpose", "what does", "what can"],
        "content": "This app helps you create, manage, and track your daily tasks. You can add due dates, set priorities, organize tasks into lists, and track your progress on the dashboard."
    },
    {
        "id": "create_todo",
        "category": "tasks",
        "title": "How to create a todo",
        "keywords": ["create", "add", "new task", "new todo", "create todo", "how to add"],
        "content": "Click the + button at the top right to open the new task form. Fill in a title, choose a priority (low/medium/high), set a due date if needed, pick a list, then click Create."
    },
    {
        "id": "get_todos",
        "category": "tasks",
        "title": "How to view/filter todos",
        "keywords": ["view", "list", "get", "filter", "search", "show tasks", "show todos"],
        "content": "Your tasks are shown on the main page. Use the filter tabs (All, Active, Completed, Overdue, Today, Upcoming) to change what you see. You can also click a list name in the sidebar to show only tasks from that list."
    },
    {
        "id": "update_todo",
        "category": "tasks",
        "title": "How to update a todo",
        "keywords": ["update", "edit", "modify", "change", "how to edit"],
        "content": "Click on any task to open the edit form. You can change the title, description, priority, due date, or move it to a different list."
    },
    {
        "id": "complete_todo",
        "category": "tasks",
        "title": "How to mark a todo as complete",
        "keywords": ["complete", "done", "finish", "mark done", "mark complete"],
        "content": "Click the green Complete button on any task to mark it as done. Completed tasks are moved to the Completed filter tab. You can reopen a completed task by clicking the button again."
    },
    {
        "id": "delete_todo",
        "category": "tasks",
        "title": "How to delete a todo",
        "keywords": ["delete", "remove", "archive", "how to delete"],
        "content": "Click the trash icon on any task to delete it. You'll be asked to confirm before the task is removed."
    },
    {
        "id": "subtasks",
        "category": "tasks",
        "title": "How to manage subtasks",
        "keywords": ["subtask", "sub task", "child", "nested", "subtasks"],
        "content": "Break down a big task into smaller steps by adding subtasks. Open a task and look for the option to add subtasks. Each subtask can be completed independently."
    },
    {
        "id": "recurring",
        "category": "tasks",
        "title": "How recurring tasks work",
        "keywords": ["recurring", "repeat", "daily", "weekly", "monthly", "repeat task"],
        "content": "When creating or editing a task, turn on the recurring option and choose a pattern: daily, weekly, or monthly. The task will automatically create a new copy when you mark it complete."
    },
    {
        "id": "lists",
        "category": "lists",
        "title": "How to manage todo lists",
        "keywords": ["list", "folder", "category", "group", "todo list"],
        "content": "Lists help you group related tasks. Use the sidebar to see your lists. Click a list name to filter tasks. You can create a new list from the add task form by selecting '+ Create New List'."
    },
    {
        "id": "labels",
        "category": "labels",
        "title": "How to use labels/tags",
        "keywords": ["label", "tag", "category", "labeling"],
        "content": "Labels are tags you can attach to tasks to group them across different lists. Each label has a name and color to help you visually organize your tasks."
    },
    {
        "id": "auth",
        "category": "auth",
        "title": "Authentication and user accounts",
        "keywords": ["login", "register", "signup", "sign in", "password", "auth", "account", "profile"],
        "content": "Register with your email, username, and password. Log in with your email or username and password. Your session stays active for 24 hours. You can change your password from the profile settings."
    },
    {
        "id": "password_rules",
        "category": "auth",
        "title": "Password requirements",
        "keywords": ["password rules", "password requirements", "password format", "password strength"],
        "content": "Your password must be at least 8 characters long and include at least one uppercase letter, one lowercase letter, one number, and one special character (!@#$%^&*(),.?\":{}|<>)."
    },
    {
        "id": "dashboard",
        "category": "analytics",
        "title": "Dashboard and analytics",
        "keywords": ["dashboard", "analytics", "stats", "statistics", "overview", "summary"],
        "content": "The dashboard gives you a quick overview of your task stats: total tasks, completed vs pending, overdue items, high priority tasks, and your completion rate. Check it to track your productivity."
    },
    {
        "id": "streak",
        "category": "analytics",
        "title": "Streak tracking",
        "keywords": ["streak", "consistency", "daily", "consecutive"],
        "content": "Your streak counts how many days in a row you've completed at least one task. Keep completing tasks daily to build and maintain your streak!"
    },
    {
        "id": "priority",
        "category": "tasks",
        "title": "Priority levels and scoring",
        "keywords": ["priority", "priority score", "high", "medium", "low", "urgent", "importance"],
        "content": "Set a priority when creating a task: High (important and urgent), Medium, or Low. High priority tasks are highlighted so you don't miss them."
    },
    {
        "id": "export",
        "category": "tasks",
        "title": "How to export tasks",
        "keywords": ["export", "download", "backup", "json", "pdf", "docx"],
        "content": "You can download your tasks as a PDF or DOCX file from the chatbot section. This exports all your active tasks with their details."
    },
    {
        "id": "chatbot",
        "category": "chatbot",
        "title": "How to use the chatbot",
        "keywords": ["chatbot", "chat", "ask", "help", "assistant", "guide"],
        "content": "Just type your question here in the chat! I can help you understand how to use the app. Ask me about creating tasks, managing lists, using the dashboard, or any other feature."
    },
    {
        "id": "attachments",
        "category": "tasks",
        "title": "How file attachments work",
        "keywords": ["attachment", "file", "upload", "attach"],
        "content": "You can attach files to your tasks. Files must be under 16MB each."
    },
    {
        "id": "profile",
        "category": "auth",
        "title": "Profile management",
        "keywords": ["profile", "avatar", "preferences", "settings", "full name"],
        "content": "Open your profile to update your name, username, or avatar. You can also change your password from the profile settings."
    },
    {
        "id": "batch_ops",
        "category": "tasks",
        "title": "Batch operations on todos",
        "keywords": ["batch", "bulk", "multiple", "mass", "batch operation"],
        "content": "You can complete, delete, or move multiple tasks at once by selecting them and choosing an action."
    },
    {
        "id": "completion_rate",
        "category": "analytics",
        "title": "Completion rate calculation",
        "keywords": ["completion rate", "percentage", "progress", "rate"],
        "content": "Your completion rate shows the percentage of tasks you've finished out of your total tasks. It's tracked over the last 30 days."
    },
    {
        "id": "greeting",
        "category": "conversation",
        "title": "Greetings",
        "keywords": ["hello", "hi", "hey", "greetings", "howdy", "good morning", "good afternoon", "good evening", "yo", "sup"],
        "content": "Hello! I'm your Todo App assistant. I can help you manage tasks, explain features, or guide you through the app. What would you like to know?"
    },
    {
        "id": "how_are_you",
        "category": "conversation",
        "title": "How are you",
        "keywords": ["how are you", "how do you do", "how's it going", "what's up", "how are things"],
        "content": "I'm doing great, thanks for asking! I'm here to help you stay organized and productive. What can I assist you with today?"
    },
    {
        "id": "thanks",
        "category": "conversation",
        "title": "Thank you",
        "keywords": ["thank you", "thanks", "thank", "appreciate", "grateful", "thx"],
        "content": "You're welcome! Happy to help. If you have any other questions about managing your tasks, feel free to ask anytime."
    },
    {
        "id": "goodbye",
        "category": "conversation",
        "title": "Goodbye",
        "keywords": ["goodbye", "bye", "see you", "later", "farewell", "cya", "gotta go"],
        "content": "Goodbye! Feel free to come back anytime you need help with your tasks. Have a productive day!"
    },
    {
        "id": "who_are_you",
        "category": "conversation",
        "title": "Who are you",
        "keywords": ["who are you", "what are you", "your name", "introduce yourself", "tell me about yourself"],
        "content": "I'm the Todo App Assistant! I'm here to help you get the most out of this task management app. I can explain features and guide you through using the app."
    },
    {
        "id": "what_can_you_do",
        "category": "conversation",
        "title": "What can you do",
        "keywords": ["what can you do", "help", "capabilities", "features", "what do you do", "how can you help"],
        "content": "I can help you with anything related to this Todo App! Ask me about creating tasks, managing lists, setting priorities, using due dates, organizing with labels, understanding analytics, or any other feature."
    },
    {
        "id": "organize_tasks",
        "category": "tasks",
        "title": "How to organize tasks effectively",
        "keywords": ["organize", "organize tasks", "organization", "stay organized", "manage tasks", "productivity"],
        "content": "Use lists to group tasks by project, set priorities to highlight what's important, add due dates to track deadlines, and use labels to tag tasks across different lists. The dashboard shows your overall progress."
    },
]


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r'[a-z0-9]+', text)
    return tokens


def compute_tf(text_tokens: List[str]) -> Dict[str, float]:
    term_count = Counter(text_tokens)
    total = len(text_tokens)
    if total == 0:
        return {}
    return {term: count / total for term, count in term_count.items()}


def compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    num_docs = len(documents)
    doc_freq = Counter()
    for doc in documents:
        unique_terms = set(doc)
        doc_freq.update(unique_terms)
    idf = {}
    for term, freq in doc_freq.items():
        idf[term] = math.log((num_docs + 1) / (freq + 1)) + 1
    return idf


def compute_tfidf(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    tfidf = {}
    all_terms = set(list(tf.keys()) + list(idf.keys()))
    for term in all_terms:
        tf_val = tf.get(term, 0)
        idf_val = idf.get(term, 0)
        tfidf[term] = tf_val * idf_val
    return tfidf


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    all_terms = set(list(vec1.keys()) + list(vec2.keys()))
    dot_product = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for term in all_terms:
        v1 = vec1.get(term, 0)
        v2 = vec2.get(term, 0)
        dot_product += v1 * v2
        norm1 += v1 * v1
        norm2 += v2 * v2
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (math.sqrt(norm1) * math.sqrt(norm2))


class RAGRetriever:
    def __init__(self):
        self.documents = KNOWLEDGE_BASE
        self._build_index()

    def _build_index(self):
        self.doc_tokens = []
        for doc in self.documents:
            combined_text = doc["title"] + " " + doc["content"] + " " + " ".join(doc["keywords"])
            self.doc_tokens.append(tokenize(combined_text))
        self.idf = compute_idf(self.doc_tokens)
        self.doc_vectors = []
        for tokens in self.doc_tokens:
            tf = compute_tf(tokens)
            self.doc_vectors.append(compute_tfidf(tf, self.idf))

    def _keyword_score(self, query: str, doc: dict) -> float:
        query_lower = query.lower()
        score = 0.0
        for kw in doc["keywords"]:
            if kw in query_lower:
                score += 2.0
        if doc["title"].lower() in query_lower:
            score += 3.0
        return score

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        query_tokens = tokenize(query)
        query_tf = compute_tf(query_tokens)
        query_vector = compute_tfidf(query_tf, self.idf)

        results = []
        for i, doc in enumerate(self.documents):
            tfidf_sim = cosine_similarity(query_vector, self.doc_vectors[i])
            kw_score = self._keyword_score(query, doc)
            combined_score = tfidf_sim * 0.6 + kw_score * 0.4
            if combined_score > 0:
                results.append((combined_score, doc))

        results.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(r[0], 4), "content": r[1]["content"], "title": r[1]["title"],
                 "category": r[1]["category"]} for r in results[:top_k]]


retriever = RAGRetriever()


MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


def _has_word(text: str, word: str) -> bool:
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))


def parse_natural_date(text: str) -> Optional[str]:
    """Try to extract a date from natural language and return YYYY-MM-DD or None."""
    text = text.lower().strip()
    today = datetime.utcnow()

    # "today"
    if _has_word(text, "today") or text in ("tdy",):
        return today.strftime("%Y-%m-%d")
    # "tomorrow"
    if _has_word(text, "tomorrow") or text in ("tmr", "tmrw"):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    # "next week"
    if re.search(r'\bnext\s+week\b', text):
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")
    # "next month"
    if re.search(r'\bnext\s+month\b', text):
        m = today.month + 1
        y = today.year
        if m > 12:
            m = 1
            y += 1
        return f"{y}-{m:02d}-{today.day:02d}"

    # Try "june 10" or "10 june" or "june 10 2026"
    match = re.search(r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?', text)
    if not match:
        match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\s*,?\s*(\d{4})?', text)
    if match:
        groups = match.groups()
        if groups[0] and groups[0].isdigit():
            day = int(groups[0])
            month_name = groups[1]
            year = int(groups[2]) if groups[2] else today.year
        else:
            month_name = groups[0]
            day = int(groups[1])
            year = int(groups[2]) if groups[2] else today.year
        month = MONTH_NAMES.get(month_name[:3].lower(), today.month)
        try:
            d = datetime(year, month, day)
            return d.strftime("%Y-%m-%d")
        except:
            pass

    # Try YYYY-MM-DD or DD/MM/YYYY
    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if match:
        return f"{int(match.group(1))}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if match:
        return f"{int(match.group(3))}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"

    return None


def extract_task_info_from_history(conversation_history: List[Dict]) -> dict:
    """Extract task info (title, description, due_date, list_name) from conversation history."""
    info = {"title": None, "description": None, "due_date": None, "list_name": None}
    if not conversation_history:
        return info

    user_msgs = [m["content"] for m in conversation_history if m["role"] == "user"]
    assistant_msgs = [m["content"] for m in conversation_history if m["role"] == "assistant"]

    # Check all user messages for task info
    for msg in user_msgs:
        title_match = re.search(r'(?:called|named|titled|title[:\s]+|task[:\s]+)"([^"]+)"', msg, re.IGNORECASE)
        if title_match:
            info["title"] = title_match.group(1)
        if not info["title"]:
            title_match = re.search(r"(?:called|named|titled|title[:\s]+|task[:\s]+)'([^']+)'", msg, re.IGNORECASE)
            if title_match:
                info["title"] = title_match.group(1)

        # Extract date
        date_str = parse_natural_date(msg)
        if date_str:
            info["due_date"] = date_str

        # Extract list
        list_match = re.search(r'(?:in|to|under|for)\s+(?:the\s+)?(?:list\s+)?["\']?(\w+)["\']?\s+(?:list)?', msg, re.IGNORECASE)
        if list_match and list_match.group(1).lower() not in ("the", "a", "my", "default"):
            info["list_name"] = list_match.group(1)

        # Check for description (text after "description" keyword or after a comma after title)
    return info


def get_last_assistant_msg(conversation_history: List[Dict]) -> Optional[str]:
    if not conversation_history:
        return None
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            return msg["content"]
    return None


FLOW_MARKERS = {
    "title": ["title", "name of the task", "call your task", "task name"],
    "description": ["description", "describe"],
    "list": ["which list", "list should", "what list", "list name"],
    "due_date": ["due date", "when is it due", "deadline", "set a due date"],
    "priority": ["priority", "priority level", "what priority", "importance", "high medium low"],
    "task_id": ["which task", "task id", "task number", "name of the task to mark"],
    "task_id_del": ["name of the task to delete"],
    "confirm_delete": ["confirm delete"],
    "confirm_complete": ["confirm complete"],
}


def detect_flow_step(last_bot_msg: str) -> Optional[str]:
    if not last_bot_msg:
        return None
    low = last_bot_msg.lower()
    for step, markers in FLOW_MARKERS.items():
        if any(m in low for m in markers):
            return step
    return None


DATA_STORE = {}  # session_id -> {title, description, due_date, list_name}


def reconstruct_flow_data(conversation_history: List[Dict]) -> dict:
    """Reconstruct collected task data from conversation history."""
    data = {"title": None, "description": None, "due_date": None, "list_name": None, "priority": None}
    if not conversation_history:
        return data

    for i, msg in enumerate(conversation_history):
        if msg["role"] == "user":
            c = msg["content"]
            prev = None
            for j in range(i - 1, -1, -1):
                if conversation_history[j]["role"] == "assistant":
                    prev = conversation_history[j]["content"]
                    break
            if prev:
                step = detect_flow_step(prev)
                if step == "title":
                    data["title"] = c
                elif step == "description":
                    data["description"] = "" if c.lower() == "skip" else c
                    if c.lower() != "skip" and not data["due_date"]:
                        parsed = parse_natural_date(c)
                        if parsed:
                            data["due_date"] = parsed
                elif step == "due_date":
                    parsed = parse_natural_date(c)
                    if parsed:
                        data["due_date"] = parsed
                elif step == "list":
                    data["list_name"] = None if c.lower() in ("skip", "default", "") else c
                elif step == "priority":
                    low = c.lower()
                    if any(p in low for p in ["high", "important", "urgent"]):
                        data["priority"] = "high"
                    elif any(p in low for p in ["low", "minor"]):
                        data["priority"] = "low"
                    else:
                        data["priority"] = "medium"
    return data


def handle_task_action(query: str, conversation_history: List[Dict], current_user_id: int) -> Optional[Dict]:
    """Handle task CRUD actions. Returns None if not an action query, or a dict with answer + optional action."""
    q = query.lower().strip()
    last_bot = get_last_assistant_msg(conversation_history)
    current_step = detect_flow_step(last_bot) if last_bot else None

    # === CREATE FLOW ===
    create_intent = any(k in q for k in ["create task", "add task", "new task", "make a task", "create a task", "add a task", "i want to create"])

    if create_intent or current_step:
        collected = reconstruct_flow_data(conversation_history)

        if current_step is None:
            return {
                "answer": "Sure! Let's create a new task. What's the title of the task?",
                "action": {"type": "create_flow", "step": "title"}
            }

        if current_step == "title":
            collected["title"] = query
            return {
                "answer": f"Got it, task is '{query}'. Want to add a description? (or type 'skip')",
                "action": {"type": "create_flow", "step": "description"}
            }
        elif current_step == "description":
            collected["description"] = "" if query.lower() == "skip" else query
            due = parse_natural_date(query) if query.lower() != "skip" else None
            if due:
                collected["due_date"] = due
                return {
                    "answer": f"Got it, I'll set the due for {due}. Which list should this go to? (Default, or type a list name, or 'skip')",
                    "action": {"type": "create_flow", "step": "list"}
                }
            return {
                "answer": "Nice! What's the due date? (e.g., 'tomorrow', 'June 10', '2026-06-10', or 'skip')",
                "action": {"type": "create_flow", "step": "due_date"}
            }
        elif current_step == "due_date":
            due = parse_natural_date(query) if query.lower() != "skip" else None
            collected["due_date"] = due
            due_text = due if due else "No due date"
            return {
                "answer": f"Set to {due_text}. Which list should this go to? (Default, or type a list name, or 'skip')",
                "action": {"type": "create_flow", "step": "list"}
            }
        elif current_step == "list":
            collected["list_name"] = None if query.lower() in ("skip", "default", "") else query
            return {
                "answer": "Got it! Now, what priority level? (high, medium, or low)",
                "action": {"type": "create_flow", "step": "priority"}
            }
        elif current_step == "priority":
            low = query.lower()
            if any(p in low for p in ["high", "important", "urgent"]):
                priority = "high"
            elif any(p in low for p in ["low", "minor"]):
                priority = "low"
            else:
                priority = "medium"
            collected["priority"] = priority
            due_text = collected.get("due_date") or "none"
            list_text = collected.get("list_name") or "Default"
            return {
                "answer": f"Creating task: '{collected['title']}' (priority: {priority}, list: {list_text}, due: {due_text}).",
                "action": {
                    "type": "execute_create",
                    "data": {
                        "title": collected.get("title") or "Untitled Task",
                        "description": collected.get("description") or "",
                        "due_date": collected.get("due_date"),
                        "list_name": collected.get("list_name"),
                        "priority": priority
                    }
                }
            }

    # === COMBINED QUERIES ===
    def _find_combined_action(q):
        for pat in [
            r'(.+?)\s+mark\s+(?:as\s+)?(?:complete|done)',
            r'mark\s+(.+?)\s+(?:as\s+)?(?:complete|done)',
            r'complete\s+(.+?)$',
        ]:
            m = re.search(pat, q)
            if m:
                return 'complete', m.group(1).strip()
        for pat in [
            r'delete\s+(.+?)$',
            r'(.+?)\s+delete\s*$',
        ]:
            m = re.search(pat, q)
            if m:
                return 'delete', m.group(1).strip()
        return None, None

    combined_action, combined_task = _find_combined_action(q)

    def _get_confirmed_task_name(history, marker):
        for i in range(len(history) - 1, -1, -1):
            if history[i]["role"] == "assistant" and marker in history[i]["content"].lower():
                m = re.search(r"'([^']+)'", history[i]["content"])
                if m:
                    return m.group(1)
        return None

    # === COMPLETE FLOW ===
    complete_intent = any(k in q for k in ["complete task", "mark done", "mark complete", "finish task", "done a task"])
    if combined_action == 'complete':
        return {
            "answer": f"Looking for task '{combined_task}'...",
            "action": {"type": "complete_flow", "step": "lookup_complete", "query": combined_task}
        }
    if complete_intent or current_step in ("task_id", "confirm_complete"):
        if current_step == "confirm_complete":
            if any(k in q for k in ["y", "yes", "complete", "confirm"]):
                confirmed = _get_confirmed_task_name(conversation_history, "confirm complete")
                if confirmed:
                    return {
                        "answer": f"Marking '{confirmed}' as complete...",
                        "action": {"type": "complete_flow", "step": "execute_complete", "query": confirmed}
                    }
            return {"answer": "Cancelled. Task was not marked complete.", "action": {"type": "_cancel"}}
        if current_step == "task_id":
            return {
                "answer": f"Looking for task '{query}'...",
                "action": {"type": "complete_flow", "step": "lookup_complete", "query": query}
            }
        return {
            "answer": "Please tell me the name or ID of the task to mark complete.",
            "action": {"type": "complete_flow", "step": "task_id"}
        }

    # === DELETE FLOW ===
    delete_intent = any(k in q for k in ["delete task", "remove task", "delete a task"])
    if combined_action == 'delete':
        return {
            "answer": f"Looking for task '{combined_task}'...",
            "action": {"type": "delete_flow", "step": "lookup_delete", "query": combined_task}
        }
    if delete_intent or current_step in ("task_id_del", "confirm_delete"):
        if current_step == "confirm_delete":
            if any(k in q for k in ["y", "yes", "delete", "confirm"]):
                confirmed = _get_confirmed_task_name(conversation_history, "confirm delete")
                if confirmed:
                    return {
                        "answer": f"Deleting '{confirmed}'...",
                        "action": {"type": "delete_flow", "step": "execute_delete", "query": confirmed}
                    }
            return {"answer": "Cancelled. Task was not deleted.", "action": {"type": "_cancel"}}
        if current_step == "task_id_del":
            return {
                "answer": f"Looking for task '{query}'...",
                "action": {"type": "delete_flow", "step": "lookup_delete", "query": query}
            }
        return {
            "answer": "Please tell me the name or ID of the task to delete.",
            "action": {"type": "delete_flow", "step": "task_id_del"}
        }

    # === LIST TASKS ===
    list_intent = any(k in q for k in ["list tasks", "show tasks", "my tasks", "what tasks", "show my tasks", "list my tasks"])
    if list_intent:
        return {
            "answer": "Fetching your tasks...",
            "action": {"type": "list_tasks"}
        }

    return None


def detect_greeting(query: str) -> Optional[str]:
    q = query.lower().strip()
    greetings = ["hello", "hi ", "hey", "howdy", "good morning", "good afternoon", "good evening", "yo", "sup"]
    thanks = ["thank", "thanks", "thx"]
    byes = ["bye", "goodbye", "see you", "later", "farewell"]
    howru = ["how are you", "how do you do", "how's it", "what's up", "how are things"]
    whoru = ["who are you", "what are you", "your name"]
    help_ = ["what can you do", "help", "capabilities"]

    if any(g in q for g in greetings) and len(q) < 20:
        return "Hello! I'm your Todo App assistant. I can help you manage tasks, explain features, or guide you through the app. What would you like to know?"
    if any(g in q for g in howru):
        return "I'm doing great, thanks for asking! I'm here to help you stay organized and productive. What can I assist you with today?"
    if any(g in q for g in thanks):
        return "You're welcome! Happy to help. If you have any other questions about managing your tasks, feel free to ask anytime."
    if any(g in q for g in byes):
        return "Goodbye! Feel free to come back anytime you need help with your tasks. Have a productive day!"
    if any(g in q for g in whoru):
        return "I'm the Todo App Assistant! I'm an AI-powered chatbot designed to help you get the most out of this task management application. I can explain features, answer questions about how things work, and guide you through using the app effectively."
    if any(g in q for g in help_) or q in ("?", "what"):
        return "I can help you with anything related to this Todo App! Ask me about creating tasks, managing lists, setting priorities, using due dates, organizing with labels, understanding analytics, completing tasks, recurring tasks, subtasks, exporting data, authentication, or any other feature."
    return None


def generate_response(query: str, conversation_history: List[Dict] = None) -> Dict:
    greeting_reply = detect_greeting(query)
    if greeting_reply:
        return {"answer": greeting_reply, "sources": []}

    retrieved_docs = retriever.retrieve(query, top_k=3)

    if not retrieved_docs:
        return {
            "answer": "I'm not sure about that. Try asking me about creating tasks, "
                      "managing lists, setting priorities, using the dashboard, "
                      "or any other app feature. I can also help with general task "
                      "organization tips!",
            "sources": []
        }

    best_doc = retrieved_docs[0]
    answer = best_doc["content"]

    if best_doc["score"] < 0.1:
        answer = ("Based on your question, here is relevant information:\n\n" + answer)

    if len(retrieved_docs) > 1 and retrieved_docs[1]["score"] > 0.05:
        related = []
        for doc in retrieved_docs[1:]:
            if doc["score"] > 0.05:
                related.append(doc["title"])
        if related:
            answer += "\n\nYou might also want to know about: " + ", ".join(related) + "."

    return {
        "answer": answer,
        "sources": [{"title": d["title"], "category": d["category"], "relevance": d["score"]} for d in retrieved_docs]
    }
