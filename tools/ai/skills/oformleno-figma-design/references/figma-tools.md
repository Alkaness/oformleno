# Editing and verification with the selected MCP

Contents: discovery; read/write shapes; auto-layout; fonts; assets; partial
results; snapshots; prototypes; handoff; precise source map.

## Discover, then read narrowly

The configured server name is `TalkToFigma`; tool namespace prefixes depend on
Codex. Discover the native tools by name/description rather than inventing the
prefix. If the connection was just added and no tools are available, refresh or
start a new Codex session. The local helper's `catalog` and `schema TOOL` inspect
the actual same build even before native discovery refreshes.

Start with `get_document_info`, `get_pages`, `get_selection`; then inspect only
the affected nodes using `get_node_info({nodeId, depth: 1})` or `get_nodes_info`.
Use a higher depth only when the entire subtree is needed. Hidden nodes can be
returned as stubs; `_childrenTruncated` means the tree is not complete enough to
clone by copying its specification. Re-read with enough depth first.

`get_document_info` is the current page's summary plus page list. Its `id` is a
page ID, not the Figma file key. `get_pages` identifies explicit page parents;
use returned IDs and record them. `create_page({name})` creates at document root
and does not use `parentId`. Every new design subtree/shape needs a parent.

Useful inspections:

| Need | Tools |
| --- | --- |
| Existing styles/components | `get_styles`, `get_local_components`, `get_remote_components` |
| Variables/modes | `get_variables` |
| Text and mixed runs | `scan_text_nodes`, `get_styled_text_segments`, `get_fonts_used` |
| Computed CSS | `get_css`, optionally recursive with bounded `maxNodes` |
| Geometry and nesting | `get_node_info`, `get_nodes_info` |
| Rendered appearance | `get_visual_snapshot` |

## Create a subtree

Prefer `create_node_tree({parentId, tree, index?})`. The tree is in the same
format as `get_node_info`, with optional `key` labels to find returned IDs.
These are **tool arguments**, not `batch_operations` plugin parameters.

The following is a schema example for an authorized future design operation,
not a finished or approved Oformleno mockup. Replace `PARENT_ID` with a real page
or frame ID; do not execute it as part of setup.

```json
{
  "parentId": "PARENT_ID",
  "tree": {
    "type": "FRAME",
    "key": "example-panel",
    "name": "Connection example",
    "width": 480,
    "layoutMode": "VERTICAL",
    "primaryAxisSizingMode": "AUTO",
    "counterAxisSizingMode": "FIXED",
    "paddingTop": 24,
    "paddingRight": 24,
    "paddingBottom": 24,
    "paddingLeft": 24,
    "itemSpacing": 16,
    "fills": ["#FFFFFF"],
    "children": [
      {
        "type": "TEXT",
        "key": "example-title",
        "characters": "Перевірити документ",
        "layoutSizingHorizontal": "FILL",
        "fills": ["#172033"],
        "style": {
          "fontFamily": "Inter",
          "fontWeight": 600,
          "fontSize": 24,
          "lineHeightPx": 32,
          "textAutoResize": "HEIGHT"
        }
      }
    ]
  }
}
```

Read the result's `rootId`, `ids`, `created` and `warnings` (in
`structuredContent` when available). Reuse those real IDs. A client can report a
protocol timeout after Figma applied some changes; inspect the parent for the
named subtree before another creation. Do not infer that an error means nothing
was created. The node-tree builder validates before creation and removes a
partly built tree on its own build failure, but transport failure is different.

## Edit nodes

`update_nodes` changes only supplied fields. A minimal typography update:

```json
{
  "updates": [
    {
      "nodeId": "TEXT_NODE_ID",
      "characters": "Завантажити виправлену копію",
      "style": { "fontFamily": "Inter", "fontWeight": 600, "fontSize": 16 }
    }
  ]
}
```

It cannot change a node's type or replace its children. Geometry readback fields
(`absoluteBoundingBox`, `localPosition`, `parentOffset`) are ignored on updates;
set `x`, `y`, `width`, `height` intentionally instead. Font weight alone preserves
each run's family/slant; family alone preserves weight/slant. `textRuns` use
start/end ranges or the source format documented in `node-spec.ts`.

Check per-node `succeeded`, `failed`, failures and warnings even when the top-level
call is not an error. Inspect/retry only failed nodes. `batch_operations` has
per-operation results too; it is not a transaction.

The current build removed the old MCP tools `create_frame`, `create_text`,
`set_fill_color`, `move_node`, `resize_node` and the single font/auto-layout
setters. Use node trees/updates. Some old command handlers survive **inside the
plugin** for `batch_operations`; their parameter shape is different, so read the
handler before using one. `set_current_page` is blocked even inside a batch.

## Layout properties that matter

- New frames/rectangles/ellipses have no fill unless given one; text defaults
  to black. New frames do not clip by default. Specify intended paint/clipping.
- Parent containers use `layoutMode: VERTICAL|HORIZONTAL`, padding and
  `itemSpacing`; axis sizing `AUTO` hugs content, `FIXED` uses a deliberate size.
- Child `layoutSizingHorizontal` / `layoutSizingVertical` use FIXED, HUG or FILL.
  FILL requires an auto-layout parent. HUG needs a layout frame or suitable text
  node. Avoid circular fill/hug dependencies and inspect resulting bounds.
- Wrapped text normally needs a finite/FILL width and `textAutoResize: HEIGHT`.
  `WIDTH_AND_HEIGHT` grows unwrapped text; it is not a paragraph-width control.
- Auto-layout places normal children. For an intentional overlay use
  `layoutPositioning: ABSOLUTE` with local `x`/`y`; avoid fixed coordinates for
  ordinary rows, buttons and responsive text.
- `x`/`y` are parent-local, not the canvas `absoluteBoundingBox`. Groups have
  special coordinate semantics; read the requested node's `localPosition` before
  moving it. `parentOffset` is useful for implementation/CSS, not blindly moving.
- Rotations are degrees counterclockwise; width/height are before rotation.
  Near 45 degrees a bounding box cannot recover original size reliably; read
  full `get_node_info` dimensions instead of inferring from REST bounds.
- Corner arrays are `[topLeft, topRight, bottomRight, bottomLeft]`; null keeps
  an existing corner when updating. Colors accept hex (including alpha) or
  RGB objects in the documented normalized format; use hex to avoid unit errors.

## Fonts and Ukrainian copy

Node-tree tools query Figma's available font catalog before mutation. A numeric
`fontWeight` selects the family's actual style name; closest-weight fallback is
reported as a warning. An exact unknown `fontStyle` is an error. Inspect the
available choices in the error or `load_font_async` schema; do not repeatedly
guess variants. If Figma lists zero fonts, fix its font loading first.

Validate Cyrillic glyphs by rendering real Ukrainian copy. UI typography does
not inherit DOCX Times New Roman requirements: those belong to checked documents,
not the app's visual identity. Keep missing font or rendering checks explicit in
the handoff. Never add private student text to a Figma example.

## Assets, icons and visual inspection

`scan_assets` inventories fills/vector nodes without image bytes. `get_asset`
reads a fill by hash or exports a node to a file. `set_svg` imports sanitized SVG;
use the actual icon/brand asset and its license. `set_image_fill` accepts URL or
base64; a remote image can fail independently of layout, so inspect the snapshot.
`extract_asset` works on a temporary clone, strips effects for export and returns
CSS effects; do not flatten the working design just to get an asset.

Default exports go to `figma-assets/` relative to server `cwd` (Oformleno). Keep
inspection exports there or under `tmp/`; copy only intentionally selected public
product assets to implementation folders when that task is authorized. Avoid
printing image base64 into logs or committing private design captures.

Snapshot arguments:

```json
{
  "nodeId": "FRAME_ID",
  "scale": 2,
  "maxDimension": 2000,
  "region": { "x": 0, "y": 0, "width": 800, "height": 600 }
}
```

Omit `region` for the whole frame. Region coordinates are from the node's
bounding-box top-left; this is different from moving children. The cap can
downsample large frames, so inspect regions at full scale for typography/detail.
Snapshotting a multi-selection returns the first node; target explicit IDs.
Use the tool's image result or save a needed export and actually view it. A text
description that says an image was returned is not visual verification.

## Components and prototype states

Use reusable frames/components for repeated buttons, findings, upload controls
and badges; inspect `create_component_from_node`, `create_component_set`,
`create_component_instance` and `set_instance_variant` schemas before use.
Conversions/instances can preserve or detach overrides; do not detach existing
instances to change typography globally. Use `set_reactions` for authorized
prototype links and interaction states. Read existing reactions first.

A drawn control or prototype link is not a working upload, document fix, email
send or purchase. Label handoff evidence as a mockup/prototype. Existing product
functions and truthful statuses are specified in design.md.

## Handoff to an implemented page

Record file link, page/frame/component IDs, widths, tokens, type styles,
variants/states and selected asset paths. Convert a real node link using the
actual file key and returned node ID; a page ID is not a file key.

`get_css` helps inspect properties; it is not proof of complete functional code.
`compare_to_figma` compares an implementation screenshot with a Figma snapshot.
For a Taste-governed frontend, capture the page with Taste's scripts first, then
pass its absolute PNG path as `renderPath`; this respects the upstream browser
workflow. Supply an explicit node ID and matching logical frame size. Inspect
SSIM, hot spots, color/overflow evidence and the heatmap; a high average score
can conceal a displaced heading. Do not claim a browser gate passed from a
Figma snapshot alone. Do not use comparison as authorization to implement/deploy.

## Source map for deeper analysis

Under `/home/eugen/claude-talk-to-figma-mcp/`:

| Question | Source |
| --- | --- |
| Exact registered tools | `src/talk_to_figma_mcp/tools/index.ts`, each `*-tools.ts`, live catalog |
| Node-tree tool arguments, result handling | `tools/node-tree-tools.ts` under `src/talk_to_figma_mcp/` |
| Accepted node/style/run fields and font normalization | `src/talk_to_figma_mcp/utils/node-spec.ts` |
| Read node shape / omitted defaults | `src/talk_to_figma_mcp/utils/figma-helpers.ts`, `utils/defaults.ts` |
| Routing, queue, parent validation, timeouts, `/status` | `src/socket.ts`, `src/shared/commands.ts` |
| Stdio and automatic channel/reconnect | `src/talk_to_figma_mcp/server.ts`, `config/config.ts`, `utils/websocket.ts` |
| Plugin command shapes / actual Figma execution | `src/claude_mcp_plugin/code.js` |
| Plugin endpoint, connection UI | `src/claude_mcp_plugin/ui.html`, `manifest.json` |
| Snapshots, image fills, exports | `src/talk_to_figma_mcp/tools/image-tools.ts`, `asset-tools.ts` |
| CSS extraction, pages, file-key limitation | `src/talk_to_figma_mcp/tools/document-tools.ts` and plugin `getDocumentInfo` |
| Render/compare metrics and image pipeline | `tools/verify-tools.ts`, `utils/image-compare.ts`, `utils/capture.ts` under `src/talk_to_figma_mcp/` |
| Font/list/partial-failure behavior tests | `tests/plugin/node-tree.test.ts`, `tests/unit/utils/node-spec.test.ts`, `tests/integration/node-tree-tools.test.ts` |

Source paths in the map are relative to the selected checkout, not Oformleno.
Read only relevant modules after initial setup; do not reload the whole external
repository during every ordinary design edit.
