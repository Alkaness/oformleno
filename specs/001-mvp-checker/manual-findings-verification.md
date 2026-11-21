# T022: grouped manual findings

`GATE: FAIL 30 (round 1 of 3)`

T022 meets the report acceptance criteria; the generic marketing-page gate has
not passed. Its exact remaining findings are retained below. No waivers were added.

The report now presents every manual finding in one initially closed
«Перевірте самі» disclosure after errors. Rule-level disclosures inside it
retain every location, excerpt, reason, value, citation and provenance entry.
Manual rules use compact neutral rows instead of error-card styling. Errors
and the corrected-copy action keep the primary emphasis.

## Functional evidence

- `Report`, individual findings, JSON, severity, applicability, counters and
  rule/fixer behavior are unchanged. Rendering remains deterministic and escaped.
  No manual outcomes are reclassified, truncated, or treated as errors or fixes.
- A synthetic 1,357-finding report retains all 1,357 locations in order, with
  evidence hidden initially and available through native disclosures.
- Native `<details>/<summary>` works without JavaScript in the exported HTML.
  In the web component, the manual link opens the disclosure before focusing
  its summary and scrolling to it. Rerender/reveal/reset recreates a closed block.
- Zero automatic errors with manual work remaining still says the review is
  incomplete. The applicable M01–M08 checklist, including the M06 distinction,
  is preserved. Empty reports have an explicit no-manual-findings message.
- `sh scripts/check.sh`: Ruff, formatting 93 files and **931 pytest tests pass**
  on Python 3.12.3. **121 targeted report/web/CLI/Streamlit tests pass**.
  Four added cases cover preservation/grouping, untrusted manual text and
  7/1,357 findings; integration assertions use the new visible labels.
- JavaScript syntax, whitespace and the tracked-document guard pass.
  Read-only Sol exploration and independent correctness/security/focus review
  found no blocking issues. One writer made code and Figma changes.

## Figma

The selected local TalkToFigma MCP inspected the existing design and added four
editable static states, preserving original frames:

- [Desktop collapsed](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-197),
  `553:197`, 1440×1057.
- [Desktop expanded](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-59),
  `553:59`, 1440×1675.
- [Mobile collapsed](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-111),
  `553:111`, 390×1617.
- [Mobile expanded](https://www.figma.com/design/UscSNH67vwwxTFoaTj2f1h/Untitled?node-id=553-144),
  `553:144`, 390×2400.

All four final native snapshots were inspected, including a full-resolution
mobile evidence region. Desktop HUG sizing was corrected after an initial
clipped export. An initial new desktop draft with incomplete Cyrillic export
is hidden; the final collapsed frame derives from the verified expanded frame.
No initial failed export counts as a successful check. Full handoff:
[figma-design.md](figma-design.md).

Existing software/report system: white/soot/surface palette, Funnel typography,
80/48/24 px gutters, neutral separators, primary black download control.
Voice: direct Ukrainian instructions and exact source evidence. No new marketing
hero, imagery, palette deal, animation scene or website was introduced.
Browser fonts can use the existing system fallback; exact Figma font matching
and interactive Figma prototype behavior are not claimed.

## Browser and print evidence

Ignored `tmp/t022/browser-evidence.json` records PASS on Chrome 147.0.7727.116.
Unmodified Taste scripts launch and own the only browser; the functional probe
attaches through CDP, makes no second browser and does not alter the kit.
Only generated DOCX/reports are used.

- Actual component FileReader validation, upload payload, before/after report,
  corrected Blob bytes, residual error, manual evidence, reveal/rerender/reset
  and Blob revocation pass through `scripts/verify_web_frontend.py`.
  This harness feeds actual Python results into the component; it is not a
  browser-to-Streamlit-server or hosted upload claim. Existing AppTest covers
  the real backend callbacks separately.
- Native Enter/Space activation, nested evidence visibility, visible focus ring,
  1,357 retained findings, default collapse and zero-error/incomplete state pass.
- With outer and inner disclosures both closed, print emulation exposes every
  manual finding. The actual generated PDF contains all seven laboratory
  checklist identifiers and their evidence. Offline CSP and script-free HTML
  remain intact. This is Chromium print evidence; other engines and physical
  devices were not tested. Older engines may not support `::details-content`.
- Initial sandbox browser-start failure, an unfocused keyboard probe and a stale
  debug-port probe are archived separately. The final run activates the offline
  tab, uses a fresh isolated profile and passes. Those earlier failures are
  not counted as successful product verification.
- Responsive consistency covers 1440/1024/820/768/390 and a 320px narrow walk.
  Functional basics pass: overflow, collisions, tap size, text clipping,
  names, heading order, focus, reduced motion and hidden-content checks.
  The general checker reports **142 FAIL / 36 WARN**; see scope below.
- Five-size layout and full-page Taste captures at 1440/1024/820/768/390
  were inspected. The layout check's **18 findings** concern the
  existing deliberate padding inside error cards, not clipped or overlapping
  content. A full desktop capture visibly reads `FRONTEND: PASS`.
- Standalone report performance at 1440/390: **0 FAIL / 0 WARN**, one 5.6 KiB
  compressed HTML request, zero script/font/image requests, zero long tasks
  and layout shift; three loads each. This is local HTML rendering, not the
  DOCX benchmark, Streamlit bundle/network performance or a hosted guarantee.
- Copy lint on the actual standalone report: 0 FAIL / 1 WARN for em dashes in
  source evidence. Exact source punctuation is retained. Linting the unrendered
  harness shell alone does not assess its dynamic report copy.

## Generic visual-check scope

The project Taste adaptation prioritizes dense document evidence and the
user's upload → inspect → fix → download flow over a marketing-page recipe.
In particular, the user's explicit initially collapsed manual block conflicts
with the general checker's no-accordion/no-height-change rule. It is retained.

Marketing hero/CTA/visual/moment/screen-height requirements, padded-card edge
heuristics and accordion height changes remain reported. No evidence is hidden
from the checker, no upstream files are edited, and no waivers are fabricated.
Blob fetch warnings come from the harness deliberately checking revocation.
The manual-link warning does not override the passing real component link/focus
check; standalone links jump to the operable disclosure rather than promising
automatic expansion. Full machine records/crops remain under ignored
`tmp/t022/.taste-skill/` and `.taste-skill/gate/`.

No student work, publication, commit/push, deployment, or new GitHub CI is part
of T022. T023 is separately authorized and starts only after this task's checks.

## Exact open gate findings

The user-requested disclosure and existing report evidence/layout remain in
place; this task does not redesign the report as a marketing page. The narrow
walk has zero findings. No `GATE: PASS` or `GATE: OPEN` is substituted for the
actual failed first round, and unchanged reruns are not used to exhaust rounds.

| Check | Widths | Target | Finding |
| --- | --- | --- | --- |
| hero-fill | 1440, 390 | main#report > div.columns > aside.summary "Підсумок перевірки" | the next section shows on the first screen: it starts at 415px on a 900px screen (the hero ends at 353px) |
| flush | 1440 | main#report > div.columns > aside.summary > a "Перейти до «Перевірте самі»" | aside.summary and section#findings run together: -817px between their content, on one ground |
| flush | 1440, 390 | section#findings > article.rule-group "R08 Номер та назва рисунка Кількість вис" | its last line sits 0px above the rule on top of details#manual |
| text-only | 1440, 390 | section#findings "Помилки та попередження" | the quote section is only text: no picture, icon, mock or effect in it |
| cta | 1440, 390 | main#report > div.headline | the hero has no button (the nav's does not count) |
| cta | 1440, 390 | main#report > div.columns > div.findings > section.coverage "Охоплення перевірки" | the last section before the footer ends with no button |
| off-grid | 1440, 390 | details#manual > summary.manual-summary "Перевірте самі Висновків: 7" | left edge at 97px, 17px off the page margin at 80px (12 elements, like span.meta) |
| moment-none | 1440 | (the page) | a software page (--type) deals no moment: every kind carries one, two on a long page (moments.md) |
| hero-screen | 1440 | main#report > div.headline "Звіт про оформленняОформлення друкованих" | the hero ends at 353px on a 900px screen, 547px above the fold: it ends at the fold, 1px either way (SR-1) |
| hero-screen | 1440 | main#report > div.columns "Підсумок перевіркиЗнайдено 1 помилку, 0 " | 507px of the next section shows on the first screen (from 393px on a 900px screen): nothing below the hero shows at load (SR-1) |
| section-height | 1440 | main#report > div.columns "Підсумок перевіркиЗнайдено 1 помилку, 0 " | the section is 1316px tall (1.5 screens), 416px over one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2) |
| one-section | 1440 | main#report > div.headline > h1 "Звіт про оформлення" | the screen at scroll 0px (stride 0) shows 209px of section 1 and the heading of section 1 whole and the content of 2 sections, over 24px each beside section 2: a screen shows one section (another may peek 8px, 24px WARN) (SR-4) |
| one-heading | 1440 | h2#findings-title "Помилки та попередження" | the section holds 4 h2 headings: one per section, first in its .wrap (SR-5) |
| container-edges | 1440 | output#qa-status "FRONTEND: PASS — FileReader, validation," | a <output> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | 1440 | div#mount ":root { color-scheme: light; --ink: #0f0" | a <div> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | 1440 | main#report > div.headline "Звіт про оформленняОформлення друкованих" | the section needs exactly one in-flow child .wrap (it has 5 in-flow children, 0 .wrap) (and 1 more like it: "Підсумок перевіркиЗнайде") (SR-6) |
| container-edges | 1440 | h2#summary-title "Підсумок перевірки" | the h2 starts 952px right of the container's left: every h1 and h2 starts on it, 2px either way (SR-6) |
| container-edges | 1440 | div.finding > div.provenance > ul > li:nth-of-type(1) "Розташування: Зразок, обраний користувач" | 2 text blocks start on a left line at x 145, 65px from the container's left: text starts on the container's left, or on one split line (x 623, 732, 841) (also "Нумерація: Зразок, обраний корис") (SR-6) |
| container-edges | 1440 | article.rule-group > div.finding > div.values > p.value-label:nth-of-type(1) "Зараз" | 4 text blocks start on a left line at x 121, 41px from the container's left: text starts on the container's left, or on one split line (x 623, 732, 841) (also "Розмір шрифту, пт", "Потрібно", "Розмір шрифту, пт") (and 3 more like it: x 105, x 97, "Перевірте самі") (SR-6) |
| container-edges | 1440 | section#findings > article.rule-group "R08Номер та назва рисункаКількість висно" | a box over half the container wide runs 80-960px, not on the container's lines at 80-1360px (SR-6) |
| container-edges | 1440 | details#manual "Перевірте саміВисновків: 7Ручні висновки" | a box over half the container wide runs 80-960px, not on the container's lines at 80-1360px (and 1 more like it: "Охоплення перевіркиВикон") (SR-6) |
| no-visual | 390 | main#report > div.columns > aside.summary "Підсумок перевірки" | no picture, effect or mock in this section; a feature section needs a visual |
| edge-left | 1440, 390 | div.columns h3 "Номер та назва рисунка" | starts at x 141.7; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p.meta "Кількість висновків: 1" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p.location "Абзац 7" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p.excerpt "Рис. 1.1 Згенерований приклад" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p "Підпис не відповідає вимогам; фа" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Ном" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns p "Походження параметрів:" | starts at x 105; the lines are 80 and the column starts |
| edge-left | 1440 | div.columns ul "Розташування: Зразок, обраний ко" | starts at x 105; the lines are 80 and the column starts |

Gate warnings: 18. The full warning records and
all detailed consistency findings/crops remain in the ignored machine artifacts.
