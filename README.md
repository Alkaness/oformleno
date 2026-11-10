# Оформлено

Перевірка оформлення студентських робіт (.docx) за методичкою кафедри: знаходить помилки в полях, шрифтах, інтервалах, заголовках, підписах рисунків і таблиць та виправляє частину з них автоматично.

> Статус: прототип (MVP 0.1) у розробці. Командний проєкт з дисципліни «Технології розробки стартапів», Львівська політехніка.
>
> Репозиторій приватний. Перед початком будь-якої задачі спитайте user, яким інструментом її виконувати. Дизайн і мокапи — у Figma. Деталі — у [принципах проєкту](memory/constitution.md).

## Навіщо

За опитуванням 23 студентів (листопад 2026): 70% втрачали бали через оформлення за останній семестр, а найбільше студентів турбують незрозумілі вимоги (3,9 з 5) і ручна рутина (3,8 з 5). Найважливіше в сервісі для них — точність саме за методичкою кафедри.

## Як працює

1. Завантажуєте .docx і обираєте методичку (набір правил).
2. Отримуєте звіт: що не так, де саме і як виправити.
3. За бажанням завантажуєте виправлену копію файлу. Оригінал не змінюється.

## Документація розробки (Spec-Driven Development)

| Файл | Що в ньому |
| --- | --- |
| [memory/constitution.md](memory/constitution.md) | Принципи, яких тримається проєкт |
| [specs/001-mvp-checker/spec.md](specs/001-mvp-checker/spec.md) | Що робить прототип і навіщо: сценарії, вимоги, критерії приймання |
| [specs/001-mvp-checker/plan.md](specs/001-mvp-checker/plan.md) | Як це зробити технічно: стек, архітектура, формат правил |
| [specs/001-mvp-checker/tasks.md](specs/001-mvp-checker/tasks.md) | Задачі по тижнях і хто за що відповідає |
| [rulesets/lpnu-afm-kontrolna-2025.yaml](rulesets/lpnu-afm-kontrolna-2025.yaml) | Перша методичка у вигляді правил |

## Швидкий старт

Буде заповнено після задачі T005 (CLI).

## Середовище розробки

Потрібні Python 3.12 і [uv](https://docs.astral.sh/uv/getting-started/installation/).
Встановлення залежностей і спільна перевірка для розробника та CI:

```bash
uv venv
uv pip sync --require-hashes requirements-dev.lock
uv pip install --no-deps --no-build-isolation -e .
sh scripts/check.sh
```

`requirements-dev.lock` фіксує версії та хеші залежностей для Python 3.12
і Linux x86_64 (поточне середовище та CI). `scripts/check.sh` запускає Ruff,
перевірку форматування та pytest. Тести створюють синтетичні `.docx`
у тимчасовій теці; роботи в репозиторій не додаються.

Пакет має структуру `src/oformleno`. Залежності наступних етапів (CLI,
завантаження YAML, веб-демо) додаються у відповідних погоджених задачах.

Оновлення lock-файлу після зміни `pyproject.toml`:

```bash
uv pip compile pyproject.toml --group dev --python-platform x86_64-unknown-linux-gnu --python-version 3.12 --generate-hashes -o requirements-dev.lock
```

Для іншої ОС залежності потрібно розв'язати для її платформи; наведений
lock-файл перевірено лише для Linux x86_64. У поточному середовищі універсальне
розв'язання залежностей недоступне через неповний офлайн-кеш метаданих.

## Working with Codex

Start with [AGENTS.md](AGENTS.md); current user decisions are recorded in
[memory/development.md](memory/development.md). Ask user which tool to use
before each new task. Codex is authorized for T001.

[AI setup](tools/ai/README.md) includes a rule skill, a Codex context hook,
and activation instructions. The Git hook `.githooks/pre-commit` rejects
staged `.docx`/`.doc` files and runs checks. Use the user-selected
`/home/eugen/claude-talk-to-figma-mcp` for Figma design in T014a.

## GitHub і CI

Репозиторій: [Alkaness/oformleno](https://github.com/Alkaness/oformleno),
**Private**, доступ лише user. Співучасників поки не запрошувати.

Робоча гілка MVP — `001-mvp-checker`. GitHub Actions запускає
[перевірки](.github/workflows/ci.yml) після кожного push і для кожного PR:
залежності з lock-файлу, заборона документів у Git, Ruff, форматування та pytest.
Переглянути останні запуски:

```bash
gh run list --repo Alkaness/oformleno --branch 001-mvp-checker --limit 3
```

Для нового checkout налаштувати локальний Git hook:

```bash
git config core.hooksPath .githooks
```

Потім встановити середовище за інструкцією вище та активувати
[AI-налаштування](tools/ai/README.md). Стан T001 і наступні кроки —
у [списку задач](specs/001-mvp-checker/tasks.md).
