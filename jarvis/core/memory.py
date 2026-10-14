"""
JARVIS Memory & Planning — persistent context, tasks, notes, and smart routing.

Three systems:
1. Memory — facts, preferences, project context JARVIS learns from conversations
2. Tasks — to-do items with priority, due dates, project association
3. Notes — freeform context tied to projects, people, or topics

Everything stored in SQLite. Relevant memories injected into every LLM call
so JARVIS gets smarter over time.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("jarvis.memory")

DB_PATH = Path(__file__).parent / "data" / "jarvis.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,          -- 'fact', 'preference', 'project', 'person', 'decision'
            content TEXT NOT NULL,
            source TEXT DEFAULT '',      -- what conversation/context it came from
            importance INTEGER DEFAULT 5, -- 1-10, higher = more important
            created_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
            status TEXT DEFAULT 'open',     -- 'open', 'in_progress', 'done', 'cancelled'
            due_date TEXT,                  -- ISO date string
            due_time TEXT,                  -- HH:MM
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',         -- JSON array
            notes TEXT DEFAULT '',
            created_at REAL NOT NULL,
            completed_at REAL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            topic TEXT DEFAULT '',       -- project name, person, or topic
            tags TEXT DEFAULT '[]',      -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, type, source,
            content='memories', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS task_fts USING fts5(
            title, description, project, notes,
            content='tasks', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(
            title, content, topic,
            content='notes', content_rowid='id'
        );

        CREATE TABLE IF NOT EXISTS failure_episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_intent TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            arguments TEXT DEFAULT '{}',
            error_type TEXT DEFAULT '',
            error_message TEXT NOT NULL,
            root_cause TEXT DEFAULT '',
            working_fix TEXT NOT NULL,
            fix_type TEXT DEFAULT 'cli_workaround',
            success_verified INTEGER DEFAULT 1,
            created_at REAL NOT NULL,
            last_used_at REAL,
            use_count INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS ui_button_maps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            control_name TEXT NOT NULL,
            control_type TEXT DEFAULT 'Button',
            action_recipe TEXT NOT NULL,
            verified INTEGER DEFAULT 1,
            created_at REAL NOT NULL,
            last_used_at REAL,
            UNIQUE(app_name, control_name)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS failure_fts USING fts5(
            task_intent, tool_name, error_message, working_fix,
            content='failure_episodes', content_rowid='id'
        );
    """)
    conn.close()
    log.info("Memory database initialized")


# ---------------------------------------------------------------------------
# Memories — facts JARVIS learns
# ---------------------------------------------------------------------------

def remember(content: str, mem_type: str = "fact", source: str = "", importance: int = 5) -> int:
    """Store a memory. Returns the memory ID."""
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO memories (type, content, source, importance, created_at) VALUES (?, ?, ?, ?, ?)",
        (mem_type, content, source, importance, time.time())
    )
    mem_id = cur.lastrowid
    # Update FTS
    conn.execute(
        "INSERT INTO memory_fts (rowid, content, type, source) VALUES (?, ?, ?, ?)",
        (mem_id, content, mem_type, source)
    )
    conn.commit()
    conn.close()
    log.info(f"Stored memory [{mem_type}]: {content[:60]}")
    return mem_id


def _sanitize_fts_query(query: str) -> str:
    """Clean a query string for FTS5 — remove special characters that break it."""
    # Remove apostrophes, quotes, and FTS operators
    cleaned = query.replace("'", "").replace('"', "").replace("*", "").replace("-", " ")
    # Take meaningful words only
    words = [w for w in cleaned.split() if len(w) > 2]
    if not words:
        return ""
    # Join with OR for broader matching
    return " OR ".join(words[:5])


def recall(query: str, limit: int = 5) -> list[dict]:
    """Search memories by relevance. Returns most relevant matches."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT m.id, m.type, m.content, m.importance, m.created_at, m.access_count
            FROM memory_fts f
            JOIN memories m ON f.rowid = m.id
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []

    # Update access counts
    for r in results:
        conn.execute(
            "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
            (time.time(), r["id"])
        )
    conn.commit()
    conn.close()
    return [dict(r) for r in results]


def get_recent_memories(limit: int = 10) -> list[dict]:
    """Get most recent memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_important_memories(limit: int = 10) -> list[dict]:
    """Get highest importance memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY importance DESC, access_count DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(title: str, description: str = "", priority: str = "medium",
                due_date: str = "", due_time: str = "", project: str = "",
                tags: list[str] = None) -> int:
    """Create a task. Returns task ID."""
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO tasks (title, description, priority, due_date, due_time,
           project, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, priority, due_date, due_time,
         project, json.dumps(tags or []), time.time())
    )
    task_id = cur.lastrowid
    conn.execute(
        "INSERT INTO task_fts (rowid, title, description, project, notes) VALUES (?, ?, ?, ?, ?)",
        (task_id, title, description, project, "")
    )
    conn.commit()
    conn.close()
    log.info(f"Created task [{priority}]: {title}")
    return task_id


def get_open_tasks(project: str = None) -> list[dict]:
    """Get all open/in-progress tasks, optionally filtered by project."""
    conn = _get_db()
    if project:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') AND project LIKE ? ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date",
            (f"%{project}%",)
        ).fetchall()
    else:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date"
        ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_tasks_for_date(date_str: str) -> list[dict]:
    """Get tasks due on a specific date (YYYY-MM-DD)."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM tasks WHERE due_date = ? AND status != 'cancelled' ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_time",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def complete_task(task_id: int):
    """Mark a task as done."""
    conn = _get_db()
    conn.execute(
        "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
        (time.time(), task_id)
    )
    conn.commit()
    conn.close()


def search_tasks(query: str, limit: int = 10) -> list[dict]:
    """Search tasks by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT t.* FROM task_fts f
            JOIN tasks t ON f.rowid = t.id
            WHERE task_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def create_note(content: str, title: str = "", topic: str = "", tags: list[str] = None) -> int:
    """Create a note. Returns note ID."""
    conn = _get_db()
    now = time.time()
    cur = conn.execute(
        "INSERT INTO notes (title, content, topic, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, content, topic, json.dumps(tags or []), now, now)
    )
    note_id = cur.lastrowid
    conn.execute(
        "INSERT INTO note_fts (rowid, title, content, topic) VALUES (?, ?, ?, ?)",
        (note_id, title, content, topic)
    )
    conn.commit()
    conn.close()
    log.info(f"Created note: {title or content[:40]}")
    return note_id


def search_notes(query: str, limit: int = 10) -> list[dict]:
    """Search notes by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT n.* FROM note_fts f
            JOIN notes n ON f.rowid = n.id
            WHERE note_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


def get_notes_by_topic(topic: str) -> list[dict]:
    """Get all notes for a topic/project."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM notes WHERE topic LIKE ? ORDER BY updated_at DESC",
        (f"%{topic}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Context Builder — smart context for LLM calls
# ---------------------------------------------------------------------------

def build_memory_context(user_message: str) -> str:
    """Build relevant context from memories, tasks, and notes for the LLM.

    Searches for relevant memories based on what the user is talking about.
    Fast — runs FTS queries, no heavy computation.
    """
    parts = []

    # Always include: open high-priority tasks
    high_tasks = [t for t in get_open_tasks() if t["priority"] == "high"]
    if high_tasks:
        task_lines = [f"  - [{t['priority']}] {t['title']}" +
                      (f" (due {t['due_date']})" if t["due_date"] else "")
                      for t in high_tasks[:5]]
        parts.append("HIGH PRIORITY TASKS:\n" + "\n".join(task_lines))

    # Search memories relevant to what user is saying
    if len(user_message) > 5:
        relevant = recall(user_message, limit=3)
        if relevant:
            mem_lines = [f"  - [{m['type']}] {m['content']}" for m in relevant]
            parts.append("RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # Recent important memories (always available)
    important = get_important_memories(limit=3)
    if important:
        imp_lines = [f"  - {m['content']}" for m in important
                     if not any(m["content"] == r["content"] for r in (relevant if 'relevant' in dir() else []))]
        if imp_lines:
            parts.append("KEY FACTS:\n" + "\n".join(imp_lines[:3]))

    return "\n\n".join(parts) if parts else ""


def format_tasks_for_voice(tasks: list[dict]) -> str:
    """Format tasks for voice response."""
    if not tasks:
        return "No tasks on the list, sir."
    count = len(tasks)
    high = [t for t in tasks if t["priority"] == "high"]
    if count == 1:
        t = tasks[0]
        return f"One task: {t['title']}." + (f" Due {t['due_date']}." if t["due_date"] else "")
    result = f"You have {count} open tasks."
    if high:
        result += f" {len(high)} are high priority."
    top = tasks[:3]
    for t in top:
        result += f" {t['title']}."
    if count > 3:
        result += f" And {count - 3} more."
    return result


def format_plan_for_voice(tasks: list[dict], events: list[dict]) -> str:
    """Format a day plan combining tasks and calendar events."""
    if not tasks and not events:
        return "Your day looks clear, sir. No events or tasks scheduled."

    parts = []
    if events:
        parts.append(f"{len(events)} events on the calendar")
    if tasks:
        high = [t for t in tasks if t["priority"] == "high"]
        parts.append(f"{len(tasks)} tasks" + (f", {len(high)} high priority" if high else ""))

    result = f"For tomorrow: {', '.join(parts)}. "

    # List events first
    if events:
        for e in events[:3]:
            result += f"{e.get('start', '')} {e['title']}. "

    # Then high priority tasks
    if tasks:
        for t in [t for t in tasks if t["priority"] == "high"][:2]:
            result += f"Priority: {t['title']}. "

    result += "Shall I adjust anything?"
    return result


# ---------------------------------------------------------------------------
# Memory extraction — learn from conversations
# ---------------------------------------------------------------------------

async def extract_memories(user_text: str, jarvis_response: str, llm_client) -> list[str]:
    """After a conversation turn, extract any facts worth remembering.

    Uses LLMRouter to decide if anything in the exchange is worth storing.
    Returns list of memories stored.
    """
    if not llm_client or len(user_text) < 15:
        return []

    try:
        system_instruction = (
            "Extract facts worth remembering from this conversation. "
            "Only extract CONCRETE facts: preferences, decisions, names, dates, plans, goals. "
            "NOT opinions, greetings, or casual chat. "
            "Return JSON array of objects: [{\"type\": \"fact|preference|project|person|decision\", \"content\": \"...\", \"importance\": 1-10}] "
            "Return [] if nothing worth remembering. Be very selective."
        )
        
        prompt = f"User: {user_text}\nJARVIS: {jarvis_response}"
        
        if hasattr(llm_client, "generate_json"):
            items = await llm_client.generate_json(prompt, system=system_instruction, temperature=0.1)
        else:
            raise ValueError("LLM client must support generate_json (use LLMRouter)")

        # Parse JSON
        stored = []
        if isinstance(items, dict) and "memories" in items:  # Handle nested JSON cases
            items = items["memories"]
            
        for item in (items if isinstance(items, list) else []):
            if isinstance(item, dict) and "content" in item:
                remember(
                    content=item["content"],
                    mem_type=item.get("type", "fact"),
                    source=user_text[:50],
                    importance=item.get("importance", 5),
                )
                stored.append(item["content"])
        return stored
    except Exception as e:
        log.debug(f"Memory extraction failed: {e}")

    return []


# ---------------------------------------------------------------------------
# Reflexion Failure Memory & Learned Fixes Store
# ---------------------------------------------------------------------------

def record_failure_reflection(
    tool_name: str,
    error_message: str,
    working_fix: str,
    error_type: str = "",
    task_intent: str = "",
    arguments: dict = None,
    root_cause: str = "",
    fix_type: str = "cli_workaround",
    success_verified: int = 1,
) -> int:
    """Store a learned error reflection and working fix into episodic memory."""
    conn = _get_db()
    args_json = json.dumps(arguments or {})
    now = time.time()

    existing = conn.execute(
        "SELECT id, use_count FROM failure_episodes WHERE tool_name = ? AND working_fix = ?",
        (tool_name, working_fix)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE failure_episodes SET last_used_at = ?, use_count = use_count + 1, success_verified = ? WHERE id = ?",
            (now, success_verified, existing["id"])
        )
        episode_id = existing["id"]
    else:
        cur = conn.execute(
            """INSERT INTO failure_episodes 
               (task_intent, tool_name, arguments, error_type, error_message, root_cause, working_fix, fix_type, success_verified, created_at, last_used_at, use_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_intent, tool_name, args_json, error_type, error_message, root_cause, working_fix, fix_type, success_verified, now, now, 1)
        )
        episode_id = cur.lastrowid
        try:
            conn.execute(
                "INSERT INTO failure_fts (rowid, task_intent, tool_name, error_message, working_fix) VALUES (?, ?, ?, ?, ?)",
                (episode_id, task_intent, tool_name, error_message, working_fix)
            )
        except Exception as e:
            log.debug(f"Failed to update failure_fts: {e}")

    conn.commit()
    conn.close()
    log.info(f"Recorded failure reflection #{episode_id} for {tool_name} with fix_type={fix_type}")
    return episode_id


def lookup_past_fix(tool_name: str, error_text: str = "", task_intent: str = "") -> dict | None:
    """Look up a previously verified fix from episodic memory for this tool/error."""
    conn = _get_db()
    try:
        rows = conn.execute(
            """SELECT id, tool_name, arguments, error_type, error_message, root_cause, working_fix, fix_type, use_count
               FROM failure_episodes 
               WHERE tool_name = ? AND success_verified = 1
               ORDER BY use_count DESC, last_used_at DESC""",
            (tool_name,)
        ).fetchall()

        if rows:
            if error_text:
                err_clean = error_text.lower()
                for r in rows:
                    if r["error_message"].lower() in err_clean or any(k in err_clean for k in r["error_message"].lower().split() if len(k) > 4):
                        _update_fix_usage(conn, r["id"])
                        return dict(r)

            top = rows[0]
            _update_fix_usage(conn, top["id"])
            return dict(top)

        query = task_intent or error_text
        if query:
            clean_q = "".join(c for c in query if c.isalnum() or c.isspace()).strip()
            if clean_q:
                fts_rows = conn.execute(
                    """SELECT e.id, e.tool_name, e.arguments, e.error_type, e.error_message, e.root_cause, e.working_fix, e.fix_type, e.use_count
                       FROM failure_fts f
                       JOIN failure_episodes e ON e.id = f.rowid
                       WHERE failure_fts MATCH ? AND e.success_verified = 1
                       ORDER BY rank
                       LIMIT 1""",
                    (clean_q,)
                ).fetchall()
                if fts_rows:
                    hit = fts_rows[0]
                    _update_fix_usage(conn, hit["id"])
                    return dict(hit)
    except Exception as e:
        log.warning(f"Error during lookup_past_fix: {e}")
    finally:
        conn.close()
    return None


def _update_fix_usage(conn: sqlite3.Connection, episode_id: int):
    try:
        conn.execute(
            "UPDATE failure_episodes SET last_used_at = ?, use_count = use_count + 1 WHERE id = ?",
            (time.time(), episode_id)
        )
        conn.commit()
    except Exception:
        pass


def list_learned_fixes(limit: int = 20) -> list[dict]:
    """Retrieve list of learned error reflections and fixes."""
    conn = _get_db()
    rows = conn.execute(
        """SELECT id, task_intent, tool_name, error_message, working_fix, fix_type, use_count, last_used_at
           FROM failure_episodes
           ORDER BY last_used_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ui_button_mapping(app_name: str, control_name: str, control_type: str, action_recipe: str) -> None:
    """Save or update discovered UI button control recipe."""
    conn = _get_db()
    now = time.time()
    conn.execute(
        """INSERT INTO ui_button_maps (app_name, control_name, control_type, action_recipe, verified, created_at, last_used_at)
           VALUES (?, ?, ?, ?, 1, ?, ?)
           ON CONFLICT(app_name, control_name) DO UPDATE SET
               action_recipe = excluded.action_recipe,
               control_type = excluded.control_type,
               last_used_at = excluded.last_used_at""",
        (app_name.lower(), control_name.lower(), control_type, action_recipe, now, now)
    )
    conn.commit()
    conn.close()


def get_ui_button_mapping(app_name: str, control_name: str) -> dict | None:
    """Get stored UI button mapping."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM ui_button_maps WHERE app_name = ? AND control_name = ?",
        (app_name.lower(), control_name.lower())
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# Initialize on import
init_db()
