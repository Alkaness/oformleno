# Project AI setup

`AGENTS.md` defines repository instructions and per-task authorization.
`memory/development.md` records current user decisions. The focused rule skill
lives at `skills/oformleno-rule/SKILL.md`. AGENTS.md links directly to it, so an
agent can read it before automatic skill discovery is activated.

`hooks.json` defines a single Codex `SessionStart` hook. It restores a short
task reminder at startup, resume, and context compaction. The script reads only
`tasks.md`, returns JSON, and writes nothing. Check it directly with
`python3 tools/ai/session_start.py`.

The Git hook `.githooks/pre-commit` rejects staged `.docx`/`.doc` files and runs
Ruff and pytest. It never prints document contents or filenames. Configuration
sources are stored here for version control. Codex protects `.git`, `.agents`,
and `.codex` inside the workspace sandbox; updates to protected paths require
an approved command or installation from a regular terminal.

User has installed the setup from a regular terminal. The rule skill is linked
and discovered by Codex, Git uses `.githooks`, and `.codex/hooks.json` matches
the source. Fresh Codex discovery now reports the SessionStart hook as
**enabled and trusted**, with zero discovery errors (verified 2026-11-10).

If `/hooks` shows zero installed hooks, verify that this Git repository itself
is trusted. In Codex 0.167.0, trusting `/home/eugen` did not load this repository's
hooks; an explicit `projects."/home/eugen/oformleno".trust_level = "trusted"`
entry did. Isolated `hooks/list` checks returned zero hooks for parent-only trust
and one SessionStart hook for explicit repository trust. A separate project
`config.toml` was not required. Restart the Codex session after changing trust.

## Activation in a writable terminal

For a new checkout, initialize Git and run from the project root:

```bash
git config core.hooksPath .githooks
mkdir -p .agents/skills .codex
ln -s ../../tools/ai/skills/oformleno-rule .agents/skills/oformleno-rule
```

If `.codex/hooks.json` does not exist, copy `tools/ai/hooks.json` there.
Otherwise merge the event into the existing configuration, preserving other
hooks. Start a new Codex session, inspect the hook with `/hooks`, and trust its
definition. This is Codex's built-in hook execution requirement, separate from
project task approval. Changes to a hook definition or its script can require
another review.

Codex discovers project skills in `.agents/skills` and supports project hooks
in `.codex/hooks.json`; project-local hooks require project and hook trust.
Official references: [skills](https://learn.chatgpt.com/docs/build-skills),
[hooks](https://learn.chatgpt.com/docs/hooks),
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Figma

User selected `/home/eugen/claude-talk-to-figma-mcp` for design and mockups.
Connection setup and Figma work belong to separately authorized T014a. Read
that tool's README and INSTALLATION.md before connecting. Use the selected local
tool and attach the Figma file link to the task.
