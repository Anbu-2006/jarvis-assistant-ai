"""
JARVIS Proactive Follow-up Suggestions.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


@dataclass
class Suggestion:
    action_type: str  # e.g., "tests", "docs", "readme"
    text: str


def suggest_followup(
    task_type: str,
    task_description: str,
    working_dir: str = ".",
    qa_result: Optional[Any] = None,
) -> Optional[Suggestion]:
    """Suggest follow-up actions (e.g. adding unit tests or docs) based on project contents."""
    p = Path(working_dir)
    if not p.exists():
        return None

    # Check for test files or test directory
    has_tests = False
    tests_dir = p / "tests"
    if tests_dir.exists() and any(tests_dir.iterdir()):
        has_tests = True
    else:
        for f in p.glob("test_*.py"):
            has_tests = True
            break

    # If code files exist (.py/.js/.ts) and no tests, suggest writing tests
    code_files = [f for f in p.iterdir() if f.is_file() and f.suffix in (".py", ".js", ".ts")]
    if len(code_files) >= 2 and not has_tests:
        return Suggestion(
            action_type="tests",
            text="Would you like me to generate unit tests for these modules, sir?",
        )

    # Check for documentation / README
    has_readme = (p / "README.md").exists() or (p / "readme.md").exists()
    if not has_readme and len(code_files) >= 3:
        return Suggestion(
            action_type="docs",
            text="Shall I draft a README.md and documentation for this project?",
        )

    return None
