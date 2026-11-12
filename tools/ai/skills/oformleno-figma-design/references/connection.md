# Local Figma connection and fresh-session setup

Contents: architecture; installed paths; Codex activation; relay/plugin startup;
diagnostics; failure recovery; source/version notes.

## The three processes

```text
Codex --stdio JSON-RPC--> local MCP server --WebSocket--> relay
                                                         |
                                                    Figma plugin
                                                         |
                                                    open Figma file
```

- Codex starts the stdio server; its stdout is the MCP protocol.
- The separately running relay uses `http://127.0.0.1:3055/status` and
  `ws://127.0.0.1:3055`. It is not an HTTP MCP endpoint.
- The development plugin runs inside the intended Figma file and connects to the
  relay. Node-tree edits execute through the Figma Plugin API there.
- The plugin path needs no Figma token, paid account or Dev Mode. Optional REST
  tools use a personal token and cannot edit the design tree. Do not acquire a
  token merely to make normal plugin editing work.

## Installed paths

| Purpose | Path |
| --- | --- |
| Selected checkout | `/home/eugen/claude-talk-to-figma-mcp` |
| Stdio entry | `dist/talk_to_figma_mcp/server.js` under that checkout |
| Relay entry | `dist/socket.js` under that checkout |
| Plugin manifest to import | `src/claude_mcp_plugin/manifest.json` under that checkout |
| Node used by project config | `/home/eugen/.nvm/versions/node/v22.19.0/bin/node` |
| Bun for relay | `/home/eugen/.bun/bin/bun` |
| Maintained Codex server config | `tools/ai/figma-mcp.toml` in Oformleno |
| Active project config | `.codex/config.toml`, linked to the maintained source |
| Project skill | `tools/ai/skills/oformleno-figma-design/` |
| Skill discovery entry | `.agents/skills/oformleno-figma-design`, a relative symlink |
| Taste installation | `.agents/skills/design-taste-frontend/` |
| Taste source/hash | `skills-lock.json` |

These are machine-local paths; verify them after moving the checkout or upgrading
Node. Node 20+ is supported by the MCP; the installed Taste tooling requires
Node 22+. Use Node 22+ for this combined workflow. Bun is needed for this relay's
`Bun.serve`; running the relay with plain Node does not work.

## Codex activation

The project is already trusted per `memory/development.md`. Project MCP settings
are TOML under `[mcp_servers.TalkToFigma]`, unlike the `mcpServers` JSON shown for
Claude in upstream docs. Do not run `configure-claude.js` to configure Codex.
Do not overwrite user-level `~/.codex/config.toml` or replace its other settings.

On this checkout the active file points to `tools/ai/figma-mcp.toml`. Its command
starts the selected local build with an absolute Node path. The working directory
is Oformleno so exports stay under this project. The 660-second tool timeout
allows the node-tree tools' 600-second inactivity budget; it does not guarantee a
long operation will succeed. Relay progress/queue behavior still applies.

For a new checkout, create the two discovery links **only if absent**:

```bash
mkdir -p .agents/skills .codex
ln -s ../../tools/ai/skills/oformleno-figma-design .agents/skills/oformleno-figma-design
ln -s ../tools/ai/figma-mcp.toml .codex/config.toml
```

If config already exists, merge the `mcp_servers.TalkToFigma` table while preserving
other settings. If a discovery entry exists, inspect it instead of overwriting it.
Codex protects these directories; an approved terminal command may be necessary.
That sandbox approval is independent of the retired project tool-choice question.

If Taste is missing, restore it using the user's chosen installer:

```bash
npx --yes skills add Leonxlnx/taste-skill --skill design-taste-frontend --agent codex --yes
```

The lock records the installed source and computed hash; reinstallation from
upstream `main` can install a newer version. Review changes before treating a new
installation as the version originally inspected. The 40 MB upstream bundle is
local/ignored, not copied into tracked Oformleno source.

Start a fresh Codex session after MCP configuration changes if `TalkToFigma` tools
are not available. Inspect the MCP list, without dumping environment secrets:

```bash
codex mcp list
```

An enabled stdio entry can display `Auth: Unsupported`; this is not a connection
failure. This plugin path has no OAuth login flow. Verify it with the real probe.

Current official references:
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp) and
[project skill discovery](https://learn.chatgpt.com/docs/build-skills).
Use actual local config/help when the installed client's behavior differs.

## Start and connect

From Oformleno:

```bash
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs status
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs relay-start
```

The launcher reuses a healthy status endpoint. Otherwise it starts the selected
Bun relay on loopback, with diagnostics in `tmp/figma-mcp/relay.log` and an owned
PID hint in `tmp/figma-mcp/relay.pid`. It does not kill another process, rebuild the
external checkout or install dependencies. A refused connection inside a sandbox
does not prove the host relay is absent; retry the health check with the proper
execution permission before diagnosing the host. Keep debug logging disabled.

The foreground alternative, run from the selected checkout, is:

```bash
/home/eugen/.bun/bin/bun run socket
```

`npm run socket` also calls Bun in this checkout. If compiled `dist/` is missing
or stale, inspect the checkout status first, then use its documented `bun install`
and `bun run build` when needed and authorized. Do not reinstall another package
or modify the external repository just because a plugin is disconnected.

In Figma Desktop (or the user's installed figma-linux client):

1. Open the intended editable design file.
2. Import the selected manifest using **Plugins → Development → Import plugin
   from manifest**, if it has not been imported from this checkout.
3. Run **Talk to Figma** and click **Connect**. Keep its window open.

Do not automate the user's GUI unnecessarily during infrastructure setup. If the
plugin is absent, name this action precisely; it is a connection requirement,
not a request to pick an AI tool. This task's setup can be completed while
honestly recording that live Figma reads/edits await the plugin.

With exactly one plugin connected, calls route automatically. Call document/page
reads directly; neither a channel ID nor `join_channel` is needed. With several
plugins, identify the target from the intended file and the channel shown in its
plugin UI, then `join_channel` in that same MCP session. A channel is ephemeral;
never hardcode a previous session's value.

## Verify the actual build

```bash
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs catalog
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs schema update_nodes
node tools/ai/skills/oformleno-figma-design/scripts/figma.mjs probe
```

The helper resolves the existing MCP SDK from the selected checkout's
`node_modules`; it adds no Oformleno runtime dependency. `catalog` performs a real
stdio initialize and tool/prompt/resource discovery. `probe` also checks the
relay and, with one plugin, document/page/selection reads; it prints success
metadata rather than live document contents. Exit codes: 0 complete; 2 relay
absent/plugin path not verified; 1 command, dependency, protocol or live-read
failure. `probe` makes zero design mutations. Configuration success, MCP
initialization and plugin execution are separate claims.

## Failure recovery

| Symptom | Action |
| --- | --- |
| No relay / socket connection refused | Check `/status` with host access; start or reuse the selected relay. |
| Port occupied but wrong status shape | Inspect the listener; do not kill it or bind a second unrelated server. |
| No Figma plugin connected | Open the selected development plugin in the intended file and click Connect. |
| Several plugins / ambiguous auto-route | Select the intended file and join its current channel. |
| MCP not in Codex | Verify project trust and TOML link/paths, then start a fresh session. |
| Unknown command or response shape | Close/reopen the plugin to load this checkout's current `code.js`; reimport only if its path was wrong. |
| No fonts / font cannot load | Check the actual family/styles. Restart Figma/font service if its font list is empty. Do not keep creating text with guessed fonts. |
| Timeout/disconnect after an edit | Inspect the target parent and returned IDs before replaying. Work in smaller subtrees; never blindly duplicate a creation. |
| `set_current_page` blocked | Pass the explicit page/frame `parentId`. |
| `parentId` missing | Get page/frame IDs and supply one, including inside `batch_operations`. |
| REST token missing | Plugin editing is unaffected. Use REST only when its optional capability is needed. |

The relay serializes commands per channel. Its inactivity timeout is 120 seconds,
reset by progress; the MCP reconnects with backoff. Do not treat progress as a
completed mutation. A restart can clear pending requests; inspect live state
before retrying non-idempotent operations. After fixing a known connection cause,
retry a read once; repeated failures need a concrete diagnosis, not a retry loop.

## Sources and revision

Inspected local checkout on 2026-11-11:
`0041874b5a2b3a46fc43c5246c834a73f7881e58`, package version `1.6.0`.
Source/docs may contain uncommitted changes, so the running `dist/` catalog and
actual schemas are the operational truth. README prose mentions 109 tools while
the newer reference describes 80 plugin tools plus 5 optional REST tools. Check
the catalog; do not infer missing tools from a version string or stale count.

For details, read the selected checkout's `README.md`, `INSTALLATION.md`,
`TROUBLESHOOTING.md` and the exact source paths listed in figma-tools.md.
