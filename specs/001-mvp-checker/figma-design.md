# T014a Figma design handoff

## T022 grouped manual findings supplement (2026-11-18)

User authorized T022 presentation changes. Existing approved frames are preserved.
Four new editable states on page `529:2` show the corrected-copy report with one
residual R08 error, a primary download action and seven secondary manual findings:

- [Desktop, collapsed](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-197),
  `553:197`, 1440×1057.
- [Desktop, expanded](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-59),
  `553:59`, 1440×1675.
- [Mobile, collapsed](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-111),
  `553:111`, 390×1617.
- [Mobile, expanded](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-144),
  `553:144`, 390×2400.

The selected local TalkToFigma MCP inspected the document/pages/selection and
existing report/manual frames. Creation and updates reported no warnings or
per-node failures. Desktop row sizing initially clipped children; readback and
new snapshots verify corrected HUG heights. An initial collapsed desktop export
omitted Cyrillic despite correct text metadata. That new draft is hidden;
the final collapsed state derives from the verified expanded frame, with its
manual content hidden and its control closed. Its native snapshot displays all
Ukrainian glyphs. Initial failed exports are not counted as successful evidence.

Final desktop and mobile snapshots, including a full-resolution mobile evidence
region, were visually inspected for wrapping, clipping, hierarchy and readable
source text. The existing white/soot/surface palette, Funnel typography and
80/24 px gutters are retained. Manual controls use neutral separators and smaller
headings; error cards and download retain prominence. These are static disclosure
states, not tested Figma interactions. Browser keyboard, focus, printing and
report/reset behavior are verified separately for T022.

## T009a ordinary-text mode supplement (2026-11-17)

The user's feedback authorizes this supplement and explicitly selects ordinary
text as the web default. Existing approved interface/device/landing frames are
preserved. The selected local TalkToFigma MCP added two native editable boards
on page `529:2`, below the existing designs:

- [Desktop mode control and report context](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=546-7),
  `546:7`, width 1440, control width 736.
- [Mobile mode control and report context](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=546-24),
  `546:24`, width 390, control width 342.

Both show the two closed selection states: «Звичайний текст» and «За стилями
документа», their actual Ukrainian explanations, and the report's selected mode.
The implementation uses a labelled native select, a 48px minimum target, the
existing border/radius/colors and system font fallback. Figma uses Funnel Sans.
The original upload frames supply the surrounding form layout.

Document/pages/selection and the existing desktop/mobile upload/report trees
were inspected before creation. Both node creations and subsequent updates
reported zero warnings/failures. Readback verified text/layout. Native snapshots
of desktop and mobile were inspected. The first desktop export omitted Cyrillic
glyphs despite correct text readback; changing/reinstating the text forced a
render refresh, and the final desktop export displays the full Ukrainian copy.
No screenshot from that initial export is counted as a pass. Browser evidence
and limits are in [ordinary-text-mode-verification.md](ordinary-text-mode-verification.md).
The boards illustrate the control states; no dropdown interaction is claimed
in Figma. Functional selection/upload/reset is checked separately in the browser.

Software / DOCX formatting checker. Completed 2026-11-12 under the user's explicit
T014a approval. This is a Figma mockup and prototype deliverable for T015, T016 and
the later landing implementation. It does not implement or publish those products.

## Source file and review links

The user supplied the real file link; all node links below use that file key.
The selected local Talk to Figma MCP created and inspected the editable nodes.

- [Figma file](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=0-1)
- [Design system](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-4)
- [Desktop landing](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-1028)
- [Mobile landing](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-1179)
- [Desktop upload flow](https://www.figma.com/proto/UscSNH67vwwxTFoaTj2f1h/Untitled?page-id=529%3A2&node-id=529-119&scaling=scale-down-width&content-scaling=fixed)
- [Mobile upload flow](https://www.figma.com/proto/UscSNH67vwwxTFoaTj2f1h/Untitled?page-id=529%3A2&node-id=529-768&scaling=scale-down-width&content-scaling=fixed)
- [Desktop report](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-170)
- [Corrected copy and download control](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-522)
- [Device mockups: Mac, iPad and iPhone](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2494)

Pages: `0:1` design system, `529:2` checker, `529:3` landing.

## Device mockups requested after the interface designs

The user clarified that the existing pages should stay as interface designs and
that mockups should show the service on actual device types: iPhone, iPad and Mac.
This authorized an extension of T014a, not T015/T016 implementation. Five editable
1920 × 1200 presentation boards now sit in the named section
`Мокапи · iPhone / iPad / Mac` (`529:2442`) on the checker page, below the original
frames. Creating a fourth page was rejected by Figma's three-page Starter limit;
the section preserves all three existing pages without an upgrade or sharing change.

| Presentation | Figma node |
| --- | --- |
| [Three-device service overview](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2494) | `529:2494` |
| [Mac: report and fixes](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2730) | `529:2730` |
| [iPad: document upload](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2834) | `529:2834` |
| [iPhone: corrected copy](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2907) | `529:2907` |
| [Landing on Mac and iPhone](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=529-2978) | `529:2978` |

The hardware shells, browser chrome and UI remain native editable Figma layers.
These are illustrative device silhouettes, not claims of exact current Apple
model dimensions or photographs. Logical display sizes are 1440 × 900 for Mac,
768 × 1024 for iPad, and 390 × 844 for iPhone. Browser/status areas leave content
viewports of 1440 × 856, 768 × 928 and 390 × 715 respectively. Posters scale the
entire device uniformly; long pages clip naturally inside its screen.

Mac and iPhone content was copied from the existing live source nodes with
unchanged copy, fonts, colors and values. The new iPad upload adaptation uses
the same design with a two-column field row, 40 px side padding and vertically
stacked form/scope content. Its editable source is retained as a hidden reference
`529:2443` inside the new section; none of the original designs was resized.
The mockup layers are fixed presentation copies, not new responsive components.

All five board snapshots were inspected; the iPad browser controls were corrected
and inspected again. The phone's download action is visible above its home area.
Geometry inspection, accounting for intentional screen clipping, found no visible
content outside the presentation boards. Original page child structures and deep
readbacks of all six reused original source frames match their pre-edit values.
The three original pages and 28 application/landing source frames are preserved.
No unresolved creation warnings remain; the tablet preparation warning was only
an ignored zero position in an auto-layout parent, with its final layout inspected.

The `.example` browser address is a presentation placeholder. These are static
device mockups; they do not establish testing on physical Apple hardware or
implemented browser compatibility. No prototype behavior, rule data or product
implementation was changed. No externally sourced device assets were used.

User review on 2026-11-12: “ok, i like it”. The five delivered device mockup
presentations are approved. Preserve them and the existing interface designs;
this approval does not itself authorize implementation or publication.

## User decisions

- Pricing: **show pricing as not yet announced**. Visible copy is
  “Ціни ще не оголошено”. There are no numeric prices, free-plan promises,
  subscriptions, payment controls or account flows.
- Remove the hero label “КАФЕДРА ЕОМ · 2026” from the landing, as requested
  with the user's screenshot. Removed from the visible layout at all four widths.
  The checker selector and factual scope explanations still identify the supported
  EOM profile; this removal does not change rule coverage or authorize other profiles.
- Use only synthetic examples. No student documents, excerpts or screenshots
  were uploaded to Figma. Guideline quotations come from the active ruleset.

## Direction and reusable system

Applied `design-taste-frontend` with the Oformleno Figma adaptation. The subject is
Oformleno's own editable checker UI. No stock photographs, external logos, raster
mockups, decorative shader scenes or unverified testimonials are needed.

The dealt direction is split hero / soot-pale-lime / Funnel typography, with a
type moment, “Оригінал не змінюється”, and a dark wordmark close. The dealt
photo-dependent nav-cards recipe was adapted to a plain navigation suitable for
software UI. Desktop landing: five sections, each 1440 × 900. Smaller frames stack
the copy and UI with content-driven heights. Equal gutters are 80 px desktop,
48 px tablet and 24 px mobile. The hero CTA is “Перевірити документ”.

Funnel Display Regular provides headings; Funnel Sans Regular/Medium provides
body copy and controls. Ukrainian glyphs were visually checked. Times New Roman
was unavailable in Figma; the before/after view therefore shows formatting values
as interface text, rather than pretending to render a Word document in that font.
This does not change the document's required fonts or any YAML value.

Key colors:

| Role | Value |
| --- | --- |
| Landing background / primary dark ink | `#0f0f0f` |
| Landing surface | `#1a1a1a` |
| Primary light ink / app background | `#ffffff` |
| Lime accent | `#dafa9c` |
| Secondary app ink | `#5f5f5f` |
| App surface / border | `#f6f6f3` / `#dcded9` |
| Error | `#ab342b` on `#fff2ef` |
| Manual review | `#85500c` on `#fff4df` |
| Success | `#23613c` on `#edf6ef` |

The local `Оформлено / Tokens` collection has 31 variables: 17 color variables
(including the initial accent variable) and 14 spacing/radius values. 341 frame and
component fill bindings were applied successfully. Seven reusable text styles
cover display/headings, body and labels. Text remains editable; this is not a
flattened image handoff. Text styles are available locally; individual text nodes
also retain explicit font properties.

`Button / Dark` (`529:113`) and `Button / Light` (`529:114`) have Default, Hover,
Pressed, Focus, Disabled and Loading variants. Component IDs for default buttons
are `529:70` and `529:83`; loading variants are `529:2436` and `529:2438`.
Reusable action components: choose `529:94`, fix `529:96`, download `529:98`,
retry `529:100`. Error/manual/success badges, fields, finding cards and banners
use the same visual rules. Focus rings are drawn; keyboard behavior is not tested.

## Frame inventory

There are 12 checker states at each of 1440 and 390 px, plus four landing frames.
Each ID below identifies an actual node in the linked Figma file.

| Checker state | Desktop node | Mobile node |
| --- | --- | --- |
| Idle upload | `529:119` | `529:768` |
| File selected | `529:334` | `529:1501` |
| Checking | `529:385` | `529:1551` |
| Findings / fix available | `529:170` | `529:253` |
| Manual checklist, original report | `529:439` | `529:818` |
| Fixing | `529:572` | `529:1604` |
| Corrected copy / residual finding / download | `529:522` | `529:897` |
| Manual checklist, corrected copy | `529:1330` | `529:1706` |
| No automatic errors, manual review remains | `529:658` | `529:996` |
| Manual checklist, no automatic errors | `529:1417` | `529:1789` |
| Invalid upload format | `529:714` | `529:943` |
| Processing failure / retry | `529:694` | `529:1686` |

| Landing width | Node |
| --- | --- |
| 1440 | `529:1028` |
| 1024 | `529:1869` |
| 768 | `529:2020` |
| 390 | `529:1179` |

## Report content contract

The illustrative report has four errors, three available fixes and seven manual
items. It uses the synthetic filename “Лабораторна робота.docx” and short generated
excerpts. R02 shows 20.00 → 25.00 mm left margin, R03 Calibri → Times New Roman,
R06 centered → justified structural heading, and R08 14 → 12 pt figure caption.
Locations, actual/expected values, exact source quotes, source labels and fixability
are visible. Quotes are not rewritten to fit a layout. Profile clarifications
are separate explanatory text.

After fixing, three corrected errors disappear, R08 remains, and all seven manual
items remain. The new filename distinguishes the corrected copy. The no-error
state explicitly says that zero automatic errors does not establish full
normative compliance. The laboratory checklist includes M01–M05, M07 and M08;
the qualification-thesis-only M06 is excluded. Manual instructions use readable
Ukrainian actions, without exposing internal implementation names in the prose.

Implementation must calculate counts, names, file sizes, locations, quotes and
fixability from actual results; these sample values are not constants. The app
shows only the selected EOM laboratory profile. Formatting checks do not evaluate
content or plagiarism. Preserve the original and process a separate copy.
The privacy and deletion copy is the intended FR-008/FR-009 behavior, not evidence
that a service has already been deployed.

## Prototype and motion

Choose file → selected → check → checking → report → fix → fixing → corrected
copy. Manual/error tabs preserve the appropriate original/ready/zero-error counts.
Header reset and failure retry links return to the relevant upload state.

Checking and fixing advance by clicking their frame in this demonstration.
The selected MCP maps timed triggers to `delay`, while the connected Figma API
requires `timeout`; automatic timeout transitions were rejected and were replaced
with persisted click transitions. No plugin source was changed. Invalid-input,
processing-failure and zero-error states are reviewable directly from the inventory;
the synthetic happy path does not randomly navigate into them.

Landing navigation scrolls within its frame. Primary landing controls open the
checker prototype URL because Figma rejects NAVIGATE actions across pages.
The report preview can open the full report. Hover/press changes use the component
variants. All 100 configured interaction sources were read back and their expected
trigger/action/destination or URL verified; inherited component reactions are allowed.

The download control is a mockup, with no generated-file action attached. The
prototype does not upload, check, fix, delete or download documents. Future motion:
one hero entrance, a brief letters-assemble treatment for the original-preservation
statement, 150 ms hover, 90 ms press, immediate focus. Reduced motion uses stable
text and color/state changes without movement. Static frames show final states;
these animation and accessibility behaviors still require implementation testing.

## Verification and limits

Native Figma snapshots were inspected for desktop and mobile upload, findings,
manual review, invalid input, checking/fixing, corrected copy, zero automatic errors,
processing failure and components. Landing review covered every desktop section,
mobile hero/comparison/pricing/FAQ/footer, and 1024/768 layouts. Corrections included
horizontal auto-layout height, findings spacing, the tablet navigation width,
the user's removed hero label, and the mobile footer wordmark wrapping.

A full subtree read of all 28 application/landing frames found no truncated
subtrees and no child bounds outside their root frames, before the final footer
font reduction. Snapshots after that reduction confirmed the mobile wordmark fits.
Creation and final updates returned no unresolved layout/font warnings. The initial
unavailable-font creation left the landing page empty; inspection preceded retry.
Rejected prototype operations were replaced with supported interactions and verified.

This is a Figma visual review, not a browser `GATE: PASS`, functional upload test,
keyboard test or implemented responsive-page test. The 1024/768 landing frames
are design references; the checker currently has desktop/mobile reference frames.
No approval of final visual design is inferred from the user's authorization to
create it. No T015/T016 code, public site, sharing change, commit, push or new
GitHub CI run is part of this task.
