# Current user decisions

- User authorized **Codex for T001 and AI setup**. T001 is still incomplete;
  stop after completing it. T002 has no tool approval.
- GitHub target: `Alkaness/oformleno`, **Private**, accessible only to user.
  Do not invite collaborators; this refines the original T001 requirements.
- Design and mockups: Figma through `/home/eugen/claude-talk-to-figma-mcp`.
  Begin design only after separate authorization for T014a.
- Refer to the decision maker as `user`. Conversation and AI-only instructions,
  skills, hooks, and memory are English. Product interfaces, reports, and error
  messages remain Ukrainian.

## Session access

- The workspace sandbox protects `.git`, `.agents`, and `.codex`.
  User resumed Codex with on-request approvals. Request escalation for Git
  metadata writes and required GitHub/network commands.
- GitHub access works in approved commands. Codex verified the repository is
  private, collaborators list contains only `Alkaness`, and no invitations are pending.
- `origin` points to `https://github.com/Alkaness/oformleno.git`. The remote
  repository is empty; the local branch is `001-mvp-checker`.
- Next: commit and push the scaffold, then verify GitHub Actions. Mark T001
  complete only after all its requirements and actual CI success are verified.

## Verified AI setup and local checks

- `core.hooksPath` is `.githooks`; the pre-commit hook is executable.
- `.agents/skills/oformleno-rule` links to the maintained source in `tools/ai/`
  and the skill appears in Codex's live catalog.
- `.codex/hooks.json` matches its maintained source. SessionStart is enabled
  and trusted, with zero discovery errors (verified 2026-11-10).
- This Git repository needs its own trusted entry in the user Codex config.
  In Codex 0.167.0, parent-folder trust alone yielded zero discovered hooks;
  explicit trust for `/home/eugen/oformleno` yielded one. A separate project
  `config.toml` was not required.
- The skill passed validation; the context hook returns valid English JSON.
- Python 3.12 package installation, Ruff, formatting, and **6 pytest tests** passed.
- `requirements-dev.lock` pins versions and hashes for Python 3.12/Linux x86_64.
  Use the setup and lock regeneration commands in `README.md`.
