# Project AI setup

`AGENTS.md` defines repository instructions and task boundaries. The standing
user choices are Codex for project work and the existing local `TalkToFigma`
MCP at `/home/eugen/claude-talk-to-figma-mcp` for Figma. Do not ask user to pick
an AI tool or Figma connector again. Older tool-choice prompts in project
documents, skills or historical memory are superseded. This applies to the main
agent and sub-agents. Checkpoint confirmation and explicit scope/holds still apply.

User approved a standing mixed-model workflow on 2026-11-12. Within an already
authorized task, use GPT-6.1 Sol for coordination/implementation, GPT-6 Luna for
focused exploration, and GPT-6.1 Sol for independent review where useful. The main
agent owns edits and final verification; exploration/review agents return findings
without editing files or Figma. Keep one Figma writer. Small tasks can stay with
one agent. No separate delegation approval is needed. See
[`AGENTS.md`](../../AGENTS.md#agent-orchestration) for the policy, model fallbacks
and task/checkpoint boundaries.

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

## Design skills and Figma

User authorized the design-infrastructure setup on 2026-11-11, explicitly holding
T014. T014a mockup creation is a separate deliverable and has not been started.
For all visual design, UI styling, mockups, landing pages and design reviews, use:

- Installed Taste Skill:
  `.agents/skills/design-taste-frontend/SKILL.md`, from `Leonxlnx/taste-skill`.
  `skills-lock.json` records its source/hash. Restore it in a fresh checkout with
  `npx --yes skills add Leonxlnx/taste-skill --skill design-taste-frontend --agent codex --yes`.
- Maintained project skill:
  [oformleno-figma-design](skills/oformleno-figma-design/SKILL.md). Its references
  cover connection/setup, actual tools/source paths, Figma editing and verification,
  and applying Taste to the project's Ukrainian product requirements.

The upstream skill is installed locally (about 40 MB), ignored with `.agents/`;
the project skill, activation helper and MCP configuration source are maintained
in this repository. An upstream reinstall can change the installed version/hash.
Upstream's Claude Stop hook is not a Codex hook; frontend gates run explicitly
when a browser implementation is actually authorized. Figma mockups use snapshots
and their own truthful review evidence, not a claimed browser gate.

Activate the maintained discovery link and project Codex MCP config:

```bash
python3 tools/ai/activate_design.py
```

It is idempotent, creates relative links to maintained sources, and refuses to
overwrite existing unrelated skill/config files. Protected `.agents`/`.codex`
writes can require sandbox approval. Existing configurations must be merged while
preserving other settings. Restart Codex if its native MCP tool list does not
refresh. Changing `session_start.py` can also require renewed hook trust in Codex.

The selected MCP remains `/home/eugen/claude-talk-to-figma-mcp`; Codex starts its
local `dist/talk_to_figma_mcp/server.js` using `tools/ai/figma-mcp.toml` linked as
`.codex/config.toml`. The relay is a separate Bun process, and the Figma plugin
must be imported from that same checkout and opened in the intended file.

```bash
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs status
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs relay-start
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs catalog
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs probe
```

The helper never changes a Figma design. `relay-start` reuses a healthy relay or
starts it on loopback, with PID/log files in ignored `tmp/figma-mcp/`. The other
commands inspect status, actual MCP schemas, and read-only live connectivity.
See the skill for exit codes and recovery. A running relay and initialized MCP
do not prove the plugin is connected. Record the real Figma file/node link when
the actual design task is completed; do not invent one from a page ID.
