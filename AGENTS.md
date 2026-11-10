# AI instructions for Oformleno

## Source of truth

At the start of a session, read these files in order:

1. `memory/constitution.md`: highest priority among project documents.
2. `specs/001-mvp-checker/spec.md`: MVP scope and acceptance criteria.
3. `specs/001-mvp-checker/plan.md`: architecture and technical decisions.
4. `specs/001-mvp-checker/tasks.md`: task dependencies and checkpoints.
5. `rulesets/lpnu-afm-kontrolna-2025.yaml`: rule parameters.

Read `memory/development.md` for current user decisions and task status.
During the session, revisit only the documents needed for the current change.

## Task authorization

- Before EACH new task, ask user which tool to use and wait for an answer.
  Authorization applies only to that task. Preserve an existing approval for
  the current task without asking again.
- Work on one task from `tasks.md`, respecting dependencies. A `[P]` label
  does not override this agreement. Delegate only if user explicitly requests it.
- If requirements conflict with the constitution or specification, or material
  requirements are unclear, stop the affected work and ask user a specific question.
- Mark `[x]` only when every requirement of the task is met. Leave partial
  tasks unchecked and record what remains. Local checks do not prove GitHub CI ran.
- After a completed task, report the result and verification, ask which tool to
  use for the next task, and stop. At checkpoints, show evidence and wait for confirmation.

## Project boundaries

- GitHub target: private `Alkaness/oformleno`, currently accessible only to user.
  Do not publish code, packages, or artifacts elsewhere.
- Never commit student work, including anonymized work. Generate test `.docx`
  files in temporary directories and commit generators only. Do not log document
  text, filenames containing personal data, or other personal information.
- Preserve the original document byte for byte; apply fixes only to a new copy.
- Product interfaces, reports, and error messages must be Ukrainian.
  Conversation and AI-only instructions, skills, hooks, and memory must be English.
- Design and mockups belong in Figma. For T014a, use
  `/home/eugen/claude-talk-to-figma-mcp` and attach the Figma file link to the task.

## Development and verification

- Use Python 3.12 and the `src/oformleno` package layout.
- Follow the environment setup in `README.md`. Run `sh scripts/check.sh` for
  Ruff, formatting, and pytest. Run targeted tests for the affected behavior.
- Update dependency declarations and their lock file together. Add dependencies
  when the authorized task needs them; do not implement future modules early.
- Each rule needs a separate implementation file and pytest coverage using
  generated or authorized `.docx` files. Before rule work, read
  `tools/ai/skills/oformleno-rule/SKILL.md`.
- Do not change YAML parameters or source quotations to fit an implementation.
  Report `manual` when reliable evaluation is impossible.
- Match verification to the change. Avoid tests that restate implementation and
  rerunning successful checks without changes or an unresolved concern.

Automation sources and activation instructions: `tools/ai/README.md`.
