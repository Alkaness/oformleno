# T015 HTML report verification

`GATE: FAIL 72 (round 1 of 3)`

T015 implements a document report, following the existing Figma report and the project-specific
Taste adaptation in `tools/ai/skills/oformleno-figma-design/references/design.md`.
The upstream marketing-page gate has not passed. Its findings are retained below, without
changing the kit, hiding report content, or manufacturing a passing result. No waivers were added.

The project adaptation explicitly says the landing-page one-section-per-screen recipe is not
a requirement for report groups, and required evidence must remain available. Its source-of-truth
Figma layout includes padded finding cards, a summary sidebar, long source labels and readable
quotes. A marketing hero, conversion buttons, decorative pictures, dealt motion and a marketing
navigation/footer are outside T015. No extra approval gate is introduced by the project skill.
The task is complete against S3 / FR-006 / FR-011; no upstream `GATE: PASS` is claimed.

## Product and code verification

- `sh scripts/check.sh`: Ruff passed, 71 files formatted, **806 pytest tests passed** on Python 3.12.3.
- 40 added cases cover HTML and CLI output. Generated DOCX covers all R01–R10, M06 applicability,
  original/after reports and actual caption-numbering failures. Arbitrary HTML-bearing report
  strings, nested values, counts, grouping, quotes, provenance, incomplete metadata, deterministic
  output and input preservation are exercised. Default JSON/exit/error behavior remains covered.
- A read-only Luna explorer mapped the contracts; a read-only Sol reviewer found one localization
  gap. The main agent fixed it and added eight generated-caption cases. Final independent review
  reported no remaining correctness findings. One writer made all edits.
- `git diff --check` and the staged-document guard passed. No real student works were accessed.
- Figma was inspected read-only through the selected local MCP: document/pages/selection,
  report/manual nodes and the desktop report snapshot. No Figma design was edited.

## Browser evidence

- Synthetic previews: ignored `tmp/t015/report.html`, `after.html`, `zero.html`. They contain
  4/3/7, 1/0/7, and 0/0/7 errors/fixable/manual findings. These are report previews, not an app.
- Headless Chromium through the unmodified Taste scripts only; checks ran sequentially.
  Loopback binding required approved host execution; the initial sandbox attempt could not bind.
- Layout snapshots: 1440×900, 1024×768, 820×1180, 768×1024 and 390×844. Desktop/mobile full-page
  captures and mobile finding/manual-evidence tiles were inspected. Final captures follow the
  compact summary and omitted empty manual-value panels. Artifacts stay under ignored `tmp/t015/`.
- Gate browser basics: off-viewport, collide, tap-size, heading-order, focus-visible, focus-hidden,
  links, accessible names and hidden-content **PASS**. Its 320×640 narrow walk has no findings
  or probe errors. The skip-link WARN is a placement heuristic; first Tab focuses the visible
  skip link and its target exists, as checked by the gate and renderer tests.
- `perf.mjs`: **PASS, 0 FAIL, 0 WARN** at 1440/390, three loads each; one request, 5.6 KiB
  compressed transfer, zero script/font/image assets, zero layout shift, zero long tasks and no
  broken requests. This is local HTML rendering evidence, not a DOCX speed benchmark (T020).
- `copy-lint`: 0 FAIL, 2 WARN. Keep the original source punctuation (em dashes) and the real
  table-formatting values it misclassifies as a statistics strip. No invented claims or prices.
- The full five-width consistency run was interrupted before completion; its partial crops are
  not counted as a completed run. The final gate completed its own 1440/390 checks and 320 walk.

## Visual scope and limits

Software / report interface; existing soot-pale-lime design, Funnel typography, neutral cards,
80/48/24 px responsive gutters and equal content edges. Voice: precise Ukrainian instructions,
source quotations verbatim, no promotional claims. Fonts use local Funnel when installed and
a system fallback otherwise, so reports make no remote font requests. Browser captures use the
fallback; exact Figma typography is not claimed. No photographs, share images, contacts, forms,
canonical domain, conversion effects or client asset slots are applicable to a private report.
Source labels use the Figma secondary ink (#5f5f5f, 6.39:1 on white); the gate misclassifies
long labels as body text requiring 7:1. All labels exceed WCAG AA normal-text contrast.

No website service, real upload/fix/download control, hosting, real-device test, GitHub CI,
commit, push or publication is claimed. T016 remains a separate, unauthorized task.

## Upstream open findings

These are the exact gate finding targets. Detailed messages/crops remain in ignored
`.taste-skill/gate.json` and `.taste-skill/gate/`; the upstream output is retained as failed.

| Check | Count |
| --- | ---: |
| `hero-fill` | 1 |
| `flush` | 2 |
| `nav` | 1 |
| `text-only` | 2 |
| `cta` | 2 |
| `text-contrast` | 1 |
| `moment-none` | 1 |
| `hero-screen` | 2 |
| `section-height` | 1 |
| `one-section` | 1 |
| `one-heading` | 1 |
| `container-edges` | 7 |
| `split-pair` | 3 |
| `no-visual` | 1 |
| `section-gaps` | 1 |
| `edge-left` | 45 |

| Check | Widths | Target |
| --- | --- | --- |
| `hero-fill` | 1440, 390 | main#report > div.columns > aside.summary "Підсумок перевірки" |
| `flush` | 1440 | h2#findings-title "Помилки та попередження" |
| `flush` | 1440, 390 | section#manual > article.rule-group.manual-group:nth-of-type(7) "M08 Інші елементи таблиці стилів Кількіс" |
| `nav` | 1440, 390 | (the first screen) |
| `text-only` | 1440, 390 | section#findings "Помилки та попередження" |
| `text-only` | 1440, 390 | section#manual "Ручні перевірки · 7" |
| `cta` | 1440, 390 | main#report > div.headline |
| `cta` | 1440, 390 | main#report > div.columns > div.findings > section.coverage "Охоплення перевірки" |
| `text-contrast` | 1440, 390 | section#findings > article.rule-group:nth-of-type(3) > div.finding > p.source "Джерело: Стилі кафедри ЕОМ · Вступ; тако" |
| `moment-none` | 1440 | (the page) |
| `hero-screen` | 1440 | main#report > div.headline "Звіт про оформленняОформлення друкованих" |
| `hero-screen` | 1440 | main#report > div.columns "Підсумок перевіркиЗнайдено 4 помилки, 3 " |
| `section-height` | 1440 | main#report > div.columns "Підсумок перевіркиЗнайдено 4 помилки, 3 " |
| `one-section` | 1440 | main#report > div.headline > h1 "Звіт про оформлення" |
| `one-heading` | 1440 | h2#findings-title "Помилки та попередження" |
| `container-edges` | 1440 | header.brand "Оформлено" |
| `container-edges` | 1440 | a.skip-link "Перейти до звіту" |
| `container-edges` | 1440 | main#report > div.headline "Звіт про оформленняОформлення друкованих" |
| `container-edges` | 1440 | h2#summary-title "Підсумок перевірки" |
| `container-edges` | 1440 | div.property > dd > ul.value-list > li:nth-of-type(1) "заголовки" |
| `container-edges` | 1440 | section#findings > article.rule-group:nth-of-type(1) "R02ПоляКількість висновків: 1Секція 1Лів" |
| `container-edges` | 1440 | section#findings > article.rule-group:nth-of-type(2) "R03Шрифт основного текстуКількість висно" |
| `split-pair` | 1440 | div.finding > div.values > dl > div.property:nth-of-type(1) "НазваВирівнюванняпо центруШрифтTimes New" |
| `split-pair` | 1440 | div.finding > div.values > dl > div.property:nth-of-type(2) "Комірки таблиціШрифтTimes New RomanРозмі" |
| `split-pair` | 1440 | div.finding > div.values > dl > div.property "Елементи для перевіркизаголовкирисункита" |
| `no-visual` | 390 | main#report > div.columns > aside.summary "Підсумок перевірки" |
| `section-gaps` | 390 | main#report > div.columns > aside.summary / section#findings |
| `edge-left` | 1440, 390 | div.columns h3 "Поля" |
| `edge-left` | 1440 | div.columns p.meta "Кількість висновків: 1" |
| `edge-left` | 1440 | div.columns p.location "Секція 1" |
| `edge-left` | 1440 | div.columns p "Ліве поле секції 1: 20.00 мм; по" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Пол" |
| `edge-left` | 1440, 390 | div.columns h3 "Шрифт основного тексту" |
| `edge-left` | 1440 | div.columns p.location "Абзац 1" |
| `edge-left` | 1440 | div.columns p.excerpt "Згенерований текст перед вступом" |
| `edge-left` | 1440 | div.columns p "Шрифт основного тексту: Calibri;" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Тек" |
| `edge-left` | 1440 | div.columns h3 "Оформлення заголовків структурни" |
| `edge-left` | 1440 | div.columns p.location "Абзац 2" |
| `edge-left` | 1440 | div.columns p.excerpt "Вступ" |
| `edge-left` | 1440 | div.columns p "Форматування структурного заголо" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Вст" |
| `edge-left` | 1440, 390 | div.columns h3 "Номер та назва рисунка" |
| `edge-left` | 1440 | div.columns p.location "Абзац 7" |
| `edge-left` | 1440 | div.columns p.excerpt "Рис. 1.1 Згенерований приклад" |
| `edge-left` | 1440 | div.columns p "Підпис не відповідає вимогам; фа" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Ном" |
| `edge-left` | 1440 | div.columns p "Походження параметрів:" |
| `edge-left` | 1440 | div.columns ul "Розташування: Зразок, обраний ко" |
| `edge-left` | 1440 | div.columns h3 "Використання обов'язкових стилів" |
| `edge-left` | 1440 | div.columns p.location "Документ загалом" |
| `edge-left` | 1440 | div.columns p "Треба звірити роль елемента, обо" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Методичні вказівки кафе" |
| `edge-left` | 1440 | div.columns h3 "Відступ і вирівнювання основного" |
| `edge-left` | 1440 | div.columns p "За вибором користувача це відсту" |
| `edge-left` | 1440 | div.columns ul "Тип відступу: Зразок, обраний ко" |
| `edge-left` | 1440 | div.columns h3 "Назва таблиці та текст у таблиця" |
| `edge-left` | 1440 | div.columns p "Перевірки R03–R05 стосуються лиш" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Наз" |
| `edge-left` | 1440 | div.columns p.source "Додаткова цитата з джерела:" |
| `edge-left` | 1440 | div.columns h3 "Автоматична нумерація та перехре" |
| `edge-left` | 1440 | div.columns p "Окрім локальних перевірок підпис" |
| `edge-left` | 1440 | div.columns h3 "Подвійні пробіли та порожні рядк" |
| `edge-left` | 1440 | div.columns p "У MVP немає окремої автоматичної" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Не " |
| `edge-left` | 1440 | div.columns h3 "Відстані колонтитулів від країв " |
| `edge-left` | 1440 | div.columns p "За вибором користувача застосову" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Від" |
| `edge-left` | 1440 | div.columns ul "Відлік відстані: Зразок, обраний" |
| `edge-left` | 1440, 390 | div.columns h3 "Інші елементи таблиці стилів" |
| `edge-left` | 1440 | div.columns p "Титульна сторінка, нумеровані за" |
| `edge-left` | 1440 | div.columns p.source "Джерело: Стилі кафедри ЕОМ · Заг" |
