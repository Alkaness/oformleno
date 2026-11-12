# Taste Skill applied to Oformleno design

## Source and scope

User installed `Leonxlnx/taste-skill` and requested it for all Oformleno design
work on 2026-11-11. The installed skill's name is `design-taste-frontend`, version
`tasteskill 2.5.1`; its unmodified files are at
`.agents/skills/design-taste-frontend/`. Provenance/hash are in `skills-lock.json`.
Read its `SKILL.md` for each relevant design task and only the references needed
for the deliverable. Before a first page it asks for `copy.md`, `copy-voice.md`,
`system.md`, `layout-v4.md` and `sections.md` in full; those paths are inside its
`references/` directory.

The user selected Figma for mockups and the existing product architecture remains
Python/Streamlit. Apply the upstream direction, copy, hierarchy, layout, assets
and critique guidance to Figma. Instructions about HTML classes, JavaScript,
browser gates or static exports apply when an implemented page is actually part
of the authorized task. Do not create a separate website, change the app stack or
deploy merely to use a frontend skill. User/project requirements take precedence
when a generic house rule conflicts with required product behavior.
Taste governs product visuals; it does not change DOCX formatting rules,
ruleset YAML parameters or source quotations.

The upstream `hooks: Stop` frontmatter describes a **Claude** hook. Installing
the skill does not install that hook into Codex. Preserve Oformleno's own hooks;
run the upstream gates explicitly for a relevant implemented frontend. Do not
claim that a missing/unsupported automatic hook ran.

## Product facts to preserve

Read the current specification before designing states or marketing claims.
Oformleno is a Ukrainian DOCX formatting checker using the selected EOM profile:

- Upload `.docx` up to 20 MiB and choose the guideline; explain invalid input.
- Show a report grouped by rules, with location, actual/expected values and
  quotations. Keep known errors, manual checks and available fixes distinguishable.
- Show the required manual checklist. Zero automatic errors with manual items
  remaining must not become “повний нормоконтроль пройдено”.
- Download a corrected **new copy**; the original stays unchanged. R08/R09 and
  other nonfixable/manual findings can remain after fixing R01–R06.
- Treat uploads privately; use generated samples in mockups. Do not upload real
  student documents/text/screenshots to Figma or outside services.
- Keep interface text, errors, reports and visible state labels Ukrainian.
  Conversation, skills and AI handoff notes are English.
- No account, payment, subscription or second-department functionality belongs
  in the MVP simply because a landing page shows pricing concepts.
- Do not invent approved prices, accuracy measurements, customer numbers,
  testimonials or successful Word checks. A pricing design can mark unresolved
  values as proposals in design annotations until user decides them.

Useful legitimate first-screen facts include the supported file format and size,
the specific guideline and preservation of the original. T014's accuracy targets
are goals, not verified marketing claims. Keep interface typography separate from
the Times New Roman requirements for checked document content.

## Different design surfaces

For the **landing page**, use the upstream software/product direction, its own
copy/section plan, restrained visual system, a real representation of Oformleno's
checker and report, and licensed assets when needed. The proposed pricing block
must reflect actual user decisions or explicit design assumptions.

For the **checker/report interface**, prioritize readable dense findings and the
upload → inspect → fix → download flow. The landing-page “one section per screen”
recipe is not a requirement to make every report group one viewport tall. Required
source quotations and explanatory report text stay visible; an upstream ban on
decorative image captions does not remove product evidence or accessible labels.

For **demo visuals**, use the actual verified product states and synthetic inputs.
Do not present a drawn UI as a live working feature or measured benchmark.

## Working in Figma

1. Inspect any established brand, typography, spacing, components and approved
   frames first. Preserve them unless a redesign was requested. Use the upstream
   brief/copy planning to identify the primary action and the subject of each view.
2. Define coherent semantic colors, type styles, spacing/radii and repeated
   component states. If brand decisions are open, use the upstream selection
   guidance; record the chosen rationale. Avoid introducing an unsupported brand
   constraint or copying a reference site's signature visuals.
3. Map the system into Figma styles/variables, auto-layout frames and reusable
   components. Keep text editable and content responsive rather than flattening
   screens into bitmap mockups. Use the selected local MCP shapes in figma-tools.md.
4. Design the required states: idle/upload, invalid input, checking, findings,
   no automatic errors with manual review, fix available, fixing, corrected copy
   ready, residual nonfixable errors and processing failure. Add mobile variants
   where the current deliverable needs them. Do not imply browser behavior was
   tested merely because these states are drawn.
5. Use real Ukrainian copy at realistic lengths. Check long rule titles, quotes,
   counts, decimal values and line wrapping. Use generated excerpts; keep unknown
   product decisions in annotations rather than fabricating confirmed facts.
6. Review actual snapshots at desktop and mobile sizes. Check equal content edges,
   hierarchy, contrast, controls, wrapping, state distinction and no clipping.
   Capture regions for detail if the tool downscaled a large frame.
7. Represent requested hover/focus/pressed/disabled and loading states as component
   variants/prototype behavior. Record reduced-motion intent in the handoff. Do
   not describe static Figma frames as tested animations, keyboard behavior or
   fully accessible implementation.

The upstream bundle includes fonts/layout/motion/photograph/icon resources. Use
those appropriate to the authorized deliverable, and preserve their licenses.
It does not require a photo collage in a document-error report or grant permission
to turn every design request into an implemented marketing website.

## Evidence for completion

For a Figma deliverable: actual file/node links, relevant frame IDs, reviewed
desktop/mobile snapshots, component states, tokens, warnings resolved or explained,
unresolved product decisions and any limits caused by unavailable fonts/plugin.
Static frames cannot receive a genuine browser `GATE: PASS`; report Figma review
as such. T014a stays unchecked until its actual mockups and Figma link are done.

For an authorized implemented frontend: follow the upstream explicit copy/layout/
consistency/screenshots/performance/gate sequence in the existing chosen stack.
Use its own foreground headless scripts, inspect screenshots and report the exact
`GATE:` outcome with remaining failures/waivers. Keep the upstream kit unmodified.
When useful, compare one of those captured PNGs with the corresponding Figma frame
using `compare_to_figma(renderPath, nodeId)`. Required browser tests, animation,
functional behavior and visual fidelity are separate evidence.

No extra design approval gate is introduced by this skill. Existing task scope,
destructive-action rules and project checkpoints still apply. Infrastructure
setup alone does not create mockups or authorize T014 real-work evaluation.
