"""
JARVIS Success Tracking — logs tasks, retries, and computes success rates.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

DEFAULT_DB = Path(__file__).parent / "jarvis_data.db"


class SuccessTracker:
    """Tracks task outcomes, retry counts, and duration across executions."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DEFAULT_DB)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS task_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                success INTEGER NOT NULL,
                retry_count INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS suggestions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                suggestion_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self.db.commit()

    def log_task(
        self,
        task_type: str,
        prompt: str,
        success: bool,
        retry_count: int = 0,
        duration: float = 0.0,
    ):
        self.db.execute(
            "INSERT INTO task_log (task_type, prompt, success, retry_count, duration_seconds, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_type, prompt, 1 if success else 0, retry_count, float(duration), datetime.now().isoformat())
        )
        self.db.commit()

    def log_suggestion(self, task_id: str, suggestion_text: str):
        self.db.execute(
            "INSERT INTO suggestions_log (task_id, suggestion_text, created_at) VALUES (?, ?, ?)",
            (str(task_id), suggestion_text, datetime.now().isoformat())
        )
        self.db.commit()

    def get_success_rate(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        if task_type:
            rows = self.db.execute(
                "SELECT success FROM task_log WHERE task_type = ?", (task_type,)
            ).fetchall()
        else:
            rows = self.db.execute("SELECT success FROM task_log").fetchall()

        total = len(rows)
        passed = sum(1 for r in rows if r["success"] == 1)
        failed = total - passed
        rate = (passed / total * 100.0) if total > 0 else 0.0
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "rate": rate,
        }

    def get_avg_duration(self, task_type: str) -> float:
        row = self.db.execute(
            "SELECT AVG(duration_seconds) as avg_d FROM task_log WHERE task_type = ?", (task_type,)
        ).fetchone()
        if row and row["avg_d"] is not None:
            return float(row["avg_d"])
        return 0.0

    def close(self):
        if self.db:
            try:
                self.db.close()
            except Exception:
                pass
