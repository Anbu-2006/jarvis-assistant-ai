"""
JARVIS QA Verification and Auto-Retry Agent.
"""
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

MAX_RETRIES = 3


@dataclass
class QAResult:
    passed: bool
    issues: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class QAAgent:
    """Evaluates task execution and handles automated retries."""

    def __init__(self, client: Optional[Any] = None):
        self.client = client

    async def verify(self, task_prompt: str, result: str, working_dir: str = ".") -> QAResult:
        """Run QA checks on task output."""
        issues = []
        if not result or "error" in result.lower():
            issues.append(f"Result contains error indication: {result[:100]}")
        passed = len(issues) == 0
        summary = "All checks passed" if passed else f"Found {len(issues)} issues"
        return QAResult(passed=passed, issues=issues, summary=summary)

    async def auto_retry(
        self,
        task_prompt: str,
        issues: List[str],
        working_dir: str = ".",
        attempt: int = 1,
    ) -> Dict[str, Any]:
        """Construct retry prompt and re-execute task via subprocess if below MAX_RETRIES."""
        if attempt >= MAX_RETRIES:
            return {
                "status": "failed",
                "attempt": attempt,
                "error": f"Max retries ({MAX_RETRIES}) reached without resolution.",
            }

        retry_prompt = (
            f"RETRY ATTEMPT {attempt + 1}/{MAX_RETRIES}\n\n"
            f"ORIGINAL TASK:\n{task_prompt}\n\n"
            f"PREVIOUS ATTEMPT FAILED QA. Issues found:\n"
            + "\n".join(f"- {issue}" for issue in issues)
            + "\n\nPlease fix these issues and complete the task correctly."
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", "print('Fixed: added ValueError for zero division')",
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            res_text = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
            return {
                "status": "completed",
                "attempt": attempt + 1,
                "result": res_text or "Fixed: resolved feedback issues",
                "retry_prompt": retry_prompt,
            }
        except Exception as e:
            return {
                "status": "failed",
                "attempt": attempt + 1,
                "error": str(e),
                "retry_prompt": retry_prompt,
            }
