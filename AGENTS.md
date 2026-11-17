# AI instructions for Oformleno

## Source of truth

At the start of a session, read these files in order:

1. `memory/constitution.md`: highest priority among project documents.
2. `specs/001-mvp-checker/spec.md`: MVP scope and acceptance criteria.
3. `specs/001-mvp-checker/plan.md`: architecture and technical decisions.
4. `specs/001-mvp-checker/tasks.md`: task dependencies and checkpoints.
5. `rulesets/lpnu-eom-styles-2026.yaml`: active rule parameters.

For EOM source revisions, recorded user clarifications, and manual checks, read
`specs/001-mvp-checker/eom-source-review.md` when working on T003 or rules.
The AFM ruleset is retained as an inactive reference.

Read `memory/development.md` for current user decisions and task status.
During the session, revisit only the documents needed for the current change.

## Task authorization

- Use Codex for project work and the selected local TalkToFigma MCP at
  `/home/eugen/claude-talk-to-figma-mcp` for Figma. These are standing user
  choices, reaffirmed on 2026-11-12; do not ask user to choose an AI tool or
  Figma connector again. Treat older tool-choice prompts in project documents,
  historical memory or skills as superseded by this instruction.
  Tool preference does not authorize unrelated tasks or bypass checkpoints.
- Work on one task from `tasks.md`, respecting dependencies. A `[P]` label
  does not override this agreement. Sub-agents may handle bounded parts of that
  same authorized task under the standing orchestration approval below.
- If requirements conflict with the constitution or specification, or material
  requirements are unclear, stop the affected work and ask user a specific question.
- Mark `[x]` only when every requirement of the task is met. Leave partial
  tasks unchecked and record what remains. Local checks do not prove GitHub CI ran.
- After a completed task, report the result and verification. Continue only
  within the user's authorized scope. At checkpoints, show evidence and wait
  for confirmation.

## Agent orchestration

- User approved this mixed-model workflow as a standing project rule on
  2026-11-12. Delegate useful independent exploration or review within an already
  authorized task without asking again. Keep small tasks with one agent when
  delegation would add unnecessary overhead.
- Prefer GPT-6.1 Sol (`gpt-6.1-sol`) as coordinator/implementer when choosing
  a main-session model. The main agent owns requirements, implementation,
  integration, resolution of review findings and final verification.
- Use GPT-6 Luna (`gpt-6-luna`) for focused repository exploration and GPT-6.1
  Sol (`gpt-6.1-sol`) for independent correctness, edge-case and test-coverage
  review. Follow an explicit user model choice; if a preferred model is
  unavailable, use a suitable available model and disclose the substitution.
- Normally use one explorer and one reviewer where useful, within the session's
  concurrency limit. Give each a bounded question, relevant context and expected
  output. Require concise findings with file references and evidence. Review
  the completed changes before final verification; parallelize only independent
  work.
- Keep one agent responsible for edits. Exploration and review sub-agents do
  not edit files or the Figma design. For shared Figma work, keep one writer.
  The main agent assesses findings, makes any needed changes and runs the
  appropriate checks before reporting the result.
- Every agent follows the same project instructions, privacy rules, permissions
  and authorized scope. Delegation does not authorize another task, publication
  or crossing a checkpoint. This standing approval replaces older requirements
  to request delegation separately; it does not authorize starting an otherwise
  unapproved task.

## Project boundaries

- GitHub target: public `Alkaness/oformleno`, by the user's explicit decision on
  2026-11-17. This visibility change does not authorize adding student work.
  Do not publish code, packages, or artifacts elsewhere.
- Never commit student work, including anonymized work. Generate test `.docx`
  files in temporary directories and commit generators only. Do not log document
  text, filenames containing personal data, or other personal information.
- Preserve the original document byte for byte; apply fixes only to a new copy.
- Product interfaces, reports, and error messages must be Ukrainian.
  Conversation and AI-only instructions, skills, hooks, and memory must be English.
- For all visual design, mockups, landing pages, UI styling and design reviews,
  use the installed `.agents/skills/design-taste-frontend/SKILL.md` together with
  `tools/ai/skills/oformleno-figma-design/SKILL.md`. The latter adapts the
  upstream workflow to Oformleno and explains connection, editing and verification.
- Design and mockups belong in Figma through the selected local `TalkToFigma`
  MCP at `/home/eugen/claude-talk-to-figma-mcp`. Attach the actual Figma file/node link
  to the relevant task. Do not substitute another Figma connector or publish
  a website unless user requests it.

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
