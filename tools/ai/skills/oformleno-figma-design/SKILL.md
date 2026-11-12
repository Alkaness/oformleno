---
name: oformleno-figma-design
description: Create, edit, inspect and verify Oformleno mockups and visual design in Figma using the selected local Talk to Figma MCP, with Taste Skill guidance. Also use for its connection setup, troubleshooting, and design-to-implementation handoff.
---

# Oformleno design in Figma

Use Codex. The selected MCP checkout is
`/home/eugen/claude-talk-to-figma-mcp`, not an npm package with a similar name.
Mockups, the landing page design and demo visuals live in Figma. Read the latest
scope/holds in `memory/development.md`; this skill does not start T014 or T014a.

## Choose the relevant instructions

- For a fresh session or connection failure, read
  [connection.md](references/connection.md). It covers installation, startup,
  Codex configuration, plugin connection and verified diagnostic commands.
- Before creating or changing a design, read the installed
  `.agents/skills/design-taste-frontend/SKILL.md` and
  [design.md](references/design.md). These apply to every Oformleno visual design,
  mockup, landing page, styling change and design review.
- For inspecting, building, editing, snapshots or implementation handoff, read
  [figma-tools.md](references/figma-tools.md). It includes current tool shapes,
  examples, partial-failure handling and the source map for deeper inspection.

Read references relative to this skill directory. Resolve project paths relative
to the Oformleno checkout. Keep AI-only notes English and product copy Ukrainian.

## Working sequence

1. Confirm the authorized deliverable from the request and task dependencies.
   Codex is the standing tool choice; do not ask about tools. Preserve checkpoint
   confirmation and task scope. Setup alone does not authorize design edits.
2. Establish the three-part connection: stdio MCP server, loopback relay, Figma
   plugin. Run `scripts/figma.mjs status` or `probe` as documented. Prefer native
   `TalkToFigma` tools once loaded in Codex; the helper uses the same local build.
3. With one plugin, call `get_document_info`, `get_pages` and `get_selection`
   directly. Do not request a channel ID or call `join_channel` first. If several
   files are connected, identify the intended file and join that plugin's channel.
   If no plugin is connected, request only the needed Figma UI action and continue
   independent preparation; do not claim live edits or verification succeeded.
4. Inspect existing pages, frames, components, styles and variables before changes.
   Keep existing work. Use explicit page/frame/node IDs in every mutation;
   `get_document_info` describes the current page, not a complete file tree.
5. Use `create_node_tree(parentId, tree)` for coherent subtrees and
   `update_nodes(updates)` for edits. New design nodes need `parentId`;
   `create_page` takes the new page's name instead.
   `set_current_page` is blocked. Prefer auto-layout with deliberate FIXED/HUG/FILL
   sizing, and the installed fonts' real family/style names.
6. Read every returned warning and per-node failure. Retain returned IDs; after
   an uncertain result, inspect the intended parent before retrying a creation.
   `update_nodes` and `batch_operations` can partially succeed.
7. Inspect `get_visual_snapshot` images of the affected desktop/mobile frames;
   correct clipping, alignment, wrapping, hierarchy, contrast and state visibility.
   A successful tool result alone does not prove a good design. Apply the
   Figma-specific Taste review in design.md; browser gates apply to an actual
   implemented page, not to static Figma frames.
8. Record the actual Figma file URL, relevant node/page IDs and verified states in
   the task/handoff. This plugin does not expose the file key in document info;
   get the real Share/Copy link instead of inventing one. Report what was checked
   and what still needs a live plugin, browser or human review.

## Local helpers

Run from the project root with Node 22+:

```bash
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs status
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs relay-start
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs catalog
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs schema create_node_tree
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs probe
```

`relay-start` starts only the local relay if absent; it reuses a healthy relay.
Other commands are read-only. `probe` initializes the actual MCP build and, when
one plugin is connected, checks document/page/selection reads without printing
document contents. It never creates a Figma node. Missing-plugin exit 2 means
the infrastructure can work but the live Figma path is not verified.

Do not enable debug payload logging, put tokens in tracked files, post comments,
change sharing, delete existing pages or publish designs as part of ordinary
setup. Use synthetic document content in previews. Keep the relay on loopback.
