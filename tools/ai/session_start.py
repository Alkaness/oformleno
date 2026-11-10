"""Restore task context without reading student documents."""

import json
import re
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    tasks = (root / "specs/001-mvp-checker/tasks.md").read_text(encoding="utf-8")
    task = next(
        (line for line in tasks.splitlines() if re.match(r"^- \[ \] \*\*T\d", line)),
        "No unfinished tasks remain.",
    )
    task_id = task.split("**")[1] if "**" in task else task
    context = (
        "Oformleno project. Follow AGENTS.md and memory/development.md. "
        "Before a new task, ask user which tool to use and wait for an answer. "
        "Preserve existing approval for the current task. Work on one task at a time "
        "and wait for confirmation at checkpoints. "
        f"First unfinished task ID (also check dependencies): {task_id}. "
        "Read its requirements in specs/001-mvp-checker/tasks.md."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
