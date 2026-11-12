"""Ukrainian CLI with machine-readable reports and sanitized failures."""

import json
from typing import Annotated, get_args

import typer
from typer.core import TyperCommand, TyperGroup

from oformleno.engine import EngineError, RuleEngine
from oformleno.fixer import FixError, fix_document
from oformleno.loader import DocumentLoadError, load_document
from oformleno.report_html import render_report_html
from oformleno.ruleset import DEFAULT_RULESET_ID, DocumentType, RulesetLoadError, load_ruleset

_ROOT_HELP = """Використання: oformleno [ПАРАМЕТРИ] КОМАНДА

Перевірка оформлення студентських робіт.

Команди:
  check    Перевірити .docx і вивести звіт JSON або HTML.
  fix      Виправити R01–R06 у новій копії та повторно перевірити її.

Параметри:
  --help, -h    Показати цю довідку.
"""

_CHECK_HELP = """Використання: oformleno check ФАЙЛ [ПАРАМЕТРИ]

Прочитати .docx до 20 МБ і вивести звіт у стандартний потік виводу.

Параметри:
  --rules НАБІР          Ідентифікатор або шлях до YAML-файлу.
                        Типово: lpnu-eom-styles-2026.
  --format ФОРМАТ       json (типово) або html — звіт для читання у браузері.
  --document-type ТИП    laboratory_report — лабораторна робота;
                        qualification_thesis — кваліфікаційна робота;
                        other_printed_work — інша друкована робота.
                        Без цього параметра застосовність уточнюється вручну.
  --help, -h            Показати цю довідку.

Коди завершення: 0 — помилок немає; 1 — знайдено помилки;
2 — помилка введення; 3 — потрібна ручна або незавершена перевірка.
"""

_FIX_HELP = """Використання: oformleno fix ФАЙЛ --output НОВИЙ_ФАЙЛ [ПАРАМЕТРИ]

Виправити надійно визначені порушення R01–R06 у новій копії .docx.
Оригінал і наявні файли не перезаписуються. Ручні висновки не виправляються.
Звіт JSON містить before, after та applied_rules. Копія повторно відкривається
й перевіряється перед збереженням.

Параметри:
  --output НОВИЙ_ФАЙЛ    Новий файл .docx для виправленої копії; обов'язковий.
  --rules НАБІР          Ідентифікатор або шлях до YAML-файлу.
                        Типово: lpnu-eom-styles-2026.
  --document-type ТИП    laboratory_report, qualification_thesis,
                        other_printed_work; без типу застосовність уточнюється вручну.
  --help, -h            Показати цю довідку.

Коди завершення за звітом копії: 0 — помилок і ручних висновків немає;
1 — лишилися помилки; 2 — помилка введення або виправлення;
3 — потрібна ручна або незавершена перевірка.
"""


class _UkrainianGroup(TyperGroup):
    def format_help(self, ctx, formatter):
        formatter.write(_ROOT_HELP)


class _UkrainianCommand(TyperCommand):
    def format_help(self, ctx, formatter):
        formatter.write(_FIX_HELP if self.name == "fix" else _CHECK_HELP)


app = typer.Typer(
    cls=_UkrainianGroup,
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _error(message: str) -> int:
    typer.echo(json.dumps({"error": message}, ensure_ascii=False), err=True)
    return 2


@app.command(cls=_UkrainianCommand)
def check(
    document: Annotated[str, typer.Argument(help="Шлях до файлу .docx.")],
    rules: Annotated[str, typer.Option("--rules", help="Набір правил або шлях до YAML.")] = (
        DEFAULT_RULESET_ID
    ),
    document_type: Annotated[
        str | None, typer.Option("--document-type", help="Тип роботи для застосовності вимог.")
    ] = None,
    report_format: Annotated[
        str, typer.Option("--format", help="Формат звіту: json або html.")
    ] = "json",
) -> int:
    if report_format not in {"json", "html"}:
        return _error("Невідомий формат звіту. Оберіть json або html.")
    if document_type is not None and document_type not in get_args(DocumentType):
        return _error("Невідомий тип роботи. Перелік значень: oformleno check --help.")
    try:
        ruleset = load_ruleset(rules)
        loaded = load_document(document)
        report = RuleEngine().check(loaded, ruleset, document_type=document_type)
    except (DocumentLoadError, RulesetLoadError, EngineError) as error:
        return _error(str(error))
    typer.echo(
        render_report_html(report) if report_format == "html" else report.model_dump_json(indent=2)
    )
    return report.exit_code()


@app.command(cls=_UkrainianCommand)
def fix(
    document: Annotated[str, typer.Argument(help="Шлях до оригінального .docx.")],
    output: Annotated[str, typer.Option("--output", help="Новий файл для виправленої копії.")],
    rules: Annotated[
        str, typer.Option("--rules", help="Набір правил або шлях до YAML.")
    ] = DEFAULT_RULESET_ID,
    document_type: Annotated[
        str | None, typer.Option("--document-type", help="Тип роботи.")
    ] = None,
) -> int:
    if document_type is not None and document_type not in get_args(DocumentType):
        return _error("Невідомий тип роботи. Перелік значень: oformleno fix --help.")
    try:
        result = fix_document(document, output, load_ruleset(rules), document_type=document_type)
    except (DocumentLoadError, RulesetLoadError, EngineError, FixError) as error:
        return _error(str(error))
    typer.echo(
        json.dumps(
            {
                "before": result.before.model_dump(mode="json"),
                "after": result.after.model_dump(mode="json"),
                "applied_rules": result.applied_rules,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result.after.exit_code()


def main() -> None:
    try:
        result = app(prog_name="oformleno", standalone_mode=False)
        code = result if isinstance(result, int) else 0
    except typer.Abort:
        typer.echo(json.dumps({"error": "Операцію перервано."}, ensure_ascii=False), err=True)
        code = 130
    except Exception:
        code = _error(
            "Не вдалося виконати команду. Перевірте аргументи. Довідка: oformleno --help."
        )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
