# T009a ordinary-text mode verification

Software / existing Ukrainian DOCX checker. User feedback on 2026-11-17
prioritized this task before T018. The user explicitly chose ordinary text as
the web default. No publication, commit, push or new GitHub CI run is claimed.

## Behavior and scope

- `ordinary` treats a direct Normal/default Word paragraph as body prose under
  the selected mode. It checks real effective font, size and line spacing with
  R03–R05 and uses the same mode for fixing/reopening/rechecking a new copy.
- `styles` retains the previous behavior and remains the API/CLI default.
  Web defaults to ordinary mode; both choices and explanations are visible.
  JSON/HTML record the mode. YAML requirements and quotes are unchanged.
- Unknown custom styles, unresolved inheritance, ambiguous structural titles,
  numbered elements, captions, objects and fields stay manual or excluded.
  Complex field results across paragraphs are guarded. Known heading, caption,
  code and table roles are not converted to prose. The mode does not infer
  roles from typography or certify all Normal paragraphs as semantically prose.
- A generated Normal/Calibri12/single-spacing paragraph produces three fixable
  errors; the corrected copy has none. The seven EOM laboratory manual checklist
  items remain. M01 is not promoted to an automatic error; no independent
  precision/recall claim is made for the new mode.

## Verification

- Final `sh scripts/check.sh`: exit 0, Ruff passed, 81 files formatted,
  **870 pytest tests passed** on Python 3.12.3. The first full run printed
  869 passed but ended with shell exit 143; the later 870-test run includes
  the added real Streamlit regression and completed with exit 0.
- 32 added cases cover the three separate body rules, valid unstyled prose,
  inherited/localized default style, known structural exclusions, unknown and
  missing styles, text plus object, cross-paragraph TOC fields, model isolation,
  mode metadata, CLI check/fix/default/error handling, web default/explicit
  selection and source-event cleanup. Real Streamlit AppTest checks ordinary
  upload, 3→0 errors, download bytes, serialized upload disposal and reset.
- Copy verification independently compares exact excluded main-body XML and
  every other ZIP member, preserves text and Normal style, and confirms source
  byte identity. Generated fixtures only; no real student work was read.
- Read-only Luna exploration and two Sol review rounds found no remaining
  correctness issue. The main agent made all source and Figma edits.
- `node --check` passed for the component; document guard and whitespace pass.

## Design and browser evidence

The established neutral checker system and Ukrainian copy are retained. No new
palette, hero, scene, stock photos, assumed claims or stand-in contacts are used.
The mode control uses a native labelled select, existing colors/radius and a
48px minimum target; Funnel falls back to system fonts without a remote request.
The [Figma supplement](figma-design.md#t009a-ordinary-text-mode-supplement-2026-11-17)
records real desktop/mobile node links, inspection and snapshot limitations.

`scripts/verify_web_frontend.py` generates isolated browser evidence using the
actual component and actual generated-DOCX check/fix results. Both desktop and
mobile foreground Taste snapshots visibly show **FRONTEND: PASS**. Assertions
cover default ordinary, explicit styles selection and explanatory copy, exact
mode in FileReader upload, disabled mode during reading, clearing filename/input,
ordinary R03/R04/R05 before and removal after fixing, residual R08 and M08,
correct Blob bytes, rerender revocation, reset and restored ordinary default.
This adapter uses precomputed Python results; it is not a live browser/server
upload claim. AppTest exercises the real server protocol separately.

Ignored evidence: `tmp/t009a/upload.html`, `frontend.html`, `upload-1440.png`,
`upload-390.png`, `consistency/`, `layout/`, `perf.json`. Representative 768 and
1024 consistency crops were also inspected. The consistency check covered
1440/1024/820/768/390 and a 320px overflow walk: no narrow overflow, collision,
tap-size, cut-text, heading-order, label, focus or contrast failure. Its quick
mode does not test every motion/reduced-motion/form condition.

Full responsive consistency: **43 FAIL / 24 WARN**. The generic marketing checks
expect hero/CTA/illustrations, viewport-height sections, .wrap class/container
patterns and no QA wrapper. Those expectations conflict with the existing dense
checker; the real mobile below-fold file/check controls are also reported as
an open usability limit. No redesign is hidden in this rule fix. Two asset
warnings correspond to intentional failed fetches of revoked Blob URLs.
Copy lint of the harness source reports 0 FAIL/0 WARN but sees only two static
words; it is not a full rendered-Ukrainian copy audit.

The separate upstream layout checker failed after its first capture with
`Cannot read properties of undefined (reading 'map')` / `r.sections is not
iterable`; no layout-script pass is claimed. The kit was not modified.
The first sandbox capture could not bind a preview port; host execution
succeeded using the same foreground Taste script.

Performance of the synthetic harness at 1440/390: **0 FAIL / 0 WARN**, 183.6 KiB,
two counted requests, no broken requests; median FCP 44/48ms, LCP 216/212ms,
blocking 18/14ms, layout shift .011/.000. The page embeds its JS, CSS, base64
fixtures and precomputed reports; parsed-JS accounting excludes inline/Blob
code. This is not a Streamlit hosting budget or a DOCX-speed T020 measurement.

## Exact final gate outcome

**`GATE: OPEN 25 (rounds used up)`**. This inherited the prior checker gate's
two rounds and used the remaining round on the new screen. No gate pass,
waiver or altered kit is claimed. There are 13 nonblocking warnings.
All 25 open targets from the exact result follow:

| Check | Widths | Target | Reason |
| --- | --- | --- | --- |
| hero-fill | 1440 | main#app-main > aside "Вимоги кафедри ЕОМ" | the next section shows on the first screen: it starts at 153px on a 900px screen (the hero ends at 991px) |
| flush | 1440 | main#app-main > section > p.app-meta "Оригінал не змінюється. Під час обробки " | section and aside run together: -821px between their content, on one ground |
| no-visual | 1440, 390 | main#app-main > section "Перевірка документа" | no picture, effect or mock in this section; a feature section needs a visual |
| cta | 1440, 390 | main#app-main > aside "Вимоги кафедри ЕОМ" | the last section before the footer ends with no button |
| moment-none | 1440 | (the page) | a software page (--type) deals no moment: every kind carries one, two on a long page (moments.md) |
| hero-screen | 1440 | main#app-main > section "Перевірка документа Завантажте .docx до " | the hero ends at 991px on a 900px screen, 91px below the fold: it ends at the fold, 1px either way (SR-1) |
| hero-screen | 1440 | main#app-main > aside "Вимоги кафедри ЕОМ НУ «Львівська політех" | 745px of the next section shows on the first screen (from 155px on a 900px screen): nothing below the hero shows at load (SR-1) |
| section-height | 1440 | main#app-main > aside "Вимоги кафедри ЕОМ НУ «Львівська політех" | the section is 836px tall (0.9 screens), 64px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2) |
| one-section | 1440 | h2#scope-title "Вимоги кафедри ЕОМ" | the screen at scroll 155px (the top of section 1) shows 836px of section 2 and the heading of section 2 whole and the content of 2 sections, over 24px each beside section 1: a screen shows one section (another may peek 8px, 24px WARN) (SR-4) |
| one-section | 1440 | main#app-main > aside "Вимоги кафедри ЕОМ НУ «Львівська політех" | a <aside> sits directly in <main>: every part of <main> is a <section> (SR-4) |
| one-heading | 1440 | main#app-main > aside > h2:nth-of-type(2) "Межі перевірки" | the section holds 2 h2 headings: one per section, first in its .wrap (SR-5) |
| one-heading | 1440 | h2#scope-title "Вимоги кафедри ЕОМ" | headings of two sections show whole on one screen at 4 of 4 scroll positions (100%; at scroll 0, 50, 100, 150px), here with ".docx": at most 3% on a desktop (SR-5) |
| container-edges | 1440 | div#oformleno-root > header.app-header "Оформлено" | the nav's content runs 88px from the left and 1211px from the right (read from its outermost blocks: no .wrap): 88 and 1211px are not one margin (one container, equal margins, 2px either way) (SR-6) |
| container-edges | 1440 | main#app-main > section "Перевірка документа Завантажте .docx до " | the content of section 1 runs 88px from the left and 596px from the right (read from its outermost blocks: no .wrap): 88 and 596px are not one margin (one container, equal margins, 2px either way) (SR-6) |
| container-edges | 1440 | output#qa-status "FRONTEND: PASS — FileReader, validation," | a <output> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | 1440 | div#mount "Перейти до перевірки Оформлено Перевірка" | a <div> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (and 2 more like it: "Перевірка документа Зава", "Вимоги кафедри ЕОМ НУ «Л") (SR-6) |
| container-edges | 1440 | main#app-main > aside > ul.app-scope > li:nth-of-type(1) "Формат сторінки та поля" | a box runs 924-1352px, outside the container lines of section 2 at 88-844px: full width is for background layers and grounds only (and 12 more like it: "Шрифт і міжрядковий інте", "Заголовки, рисунки й таб", "Нумерація сторінок") (SR-6) |
| container-edges | 1440 | main#app-main > section > div.app-dropzone > p.app-file-type ".docx" | ".docx" is set centred across 706px, over half the 756px container: text that wide is set left (and 2 more like it: "Перетягніть документ сюд", "або оберіть файл на прис") (SR-6) |
| row-lines | 1440 | main#app-main > aside > p.app-meta "Перевірка оформлення не оцінює зміст чи " | "Перевірка оформлення не оцінює з" ends at 1350px, past the container's right line at 844px (SR-7) |
| row-lines | 1440 | main#app-main > aside > p:nth-of-type(2) "Якщо роль елемента або його форматування" | "Якщо роль елемента або його форм" ends at 1281px, past the container's right line at 844px (SR-7) |
| row-lines | 1440 | main#app-main > aside > ul.app-scope > li:nth-of-type(2) "Шрифт і міжрядковий інтервал" | "Шрифт і міжрядковий інтервал" ends at 1186px, past the container's right line at 844px (and 6 more like it: "Вимоги кафедри ЕОМ", "Заголовки, рисунки й таб", "НУ «Львівська політехнік") (SR-7) |
| fold-cut | 390 | main#app-main > section > div.app-dropzone > p.app-file-type ".docx" | a 40px line is sliced by the bottom of the first screen (26px of it below the fold) |
| text-only | 390 | main#app-main > aside "Вимоги кафедри ЕОМ" | the closing section is only text: no picture, icon, mock or effect in it |
| fold-action | 390 | main#app-main > section > div.app-dropzone > button | the hero's main button "Обрати файл" starts 122px below the first screen (844px tall): it is not seen on load |
| container | 1440, 390 | page | no .wrap |
