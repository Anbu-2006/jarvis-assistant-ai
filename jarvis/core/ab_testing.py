"""
JARVIS Prompt Template A/B Testing Engine.
"""
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

DEFAULT_DB = Path(__file__).parent / "jarvis_data.db"


@dataclass
class PromptTemplate:
    name: str
    version: str
    template: str
    task_type: str = "build"


@dataclass
class VersionStats:
    version: str
    total_tasks: int = 0
    passed_tasks: int = 0
    success_rate: float = 0.0


class ABTester:
    """Manages A/B testing of prompt variations."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DEFAULT_DB)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._ensure_tables()
        self._templates: Dict[str, list[PromptTemplate]] = {
            "landing_page": [
                PromptTemplate(name="landing_page", version="v1", template="Build landing page v1", task_type="build"),
                PromptTemplate(name="landing_page", version="v2", template="Build landing page v2", task_type="build"),
            ]
        }

    def _ensure_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ab_experiments (
                id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                version TEXT NOT NULL,
                success INTEGER,
                created_at TEXT NOT NULL
            );
        """)
        self.db.commit()

    def select_template(self, template_name: str) -> Tuple[PromptTemplate, str]:
        """Select a template variant and create an experiment run."""
        variants = self._templates.get(
            template_name,
            [PromptTemplate(name=template_name, version="v1", template="", task_type="build")]
        )
        variant = variants[0]
        exp_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO ab_experiments (id, template_name, version, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (exp_id, template_name, variant.version, None, datetime.now().isoformat())
        )
        self.db.commit()
        return variant, exp_id

    def record_result(self, exp_id: str, version: str, success: bool):
        self.db.execute(
            "UPDATE ab_experiments SET success = ? WHERE id = ?",
            (1 if success else 0, exp_id)
        )
        self.db.commit()

    def get_version_stats(self, template_name: str) -> Dict[str, VersionStats]:
        rows = self.db.execute(
            "SELECT version, success FROM ab_experiments WHERE template_name = ? AND success IS NOT NULL",
            (template_name,)
        ).fetchall()
        stats_map: Dict[str, VersionStats] = {}
        for r in rows:
            v = r["version"]
            if v not in stats_map:
                stats_map[v] = VersionStats(version=v, total_tasks=0, passed_tasks=0, success_rate=0.0)
            stats_map[v].total_tasks += 1
            if r["success"] == 1:
                stats_map[v].passed_tasks += 1
        for s in stats_map.values():
            s.success_rate = (s.passed_tasks / s.total_tasks * 100.0) if s.total_tasks > 0 else 0.0
        return stats_map

    def close(self):
        if self.db:
            try:
                self.db.close()
            except Exception:
                pass
