"""Exercise loader contracts using generated DOCX packages only."""

import traceback
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest
from docx import Document

from oformleno.loader import DocumentLoadError, load_document, load_document_bytes

LIMIT_BYTES = 20 * 1024 * 1024
GENERATED_TEXT = "Згенерований абзац для перевірки завантаження."
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@pytest.fixture
def docx_content():
    document = Document()
    document.add_paragraph(GENERATED_TEXT)
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Згенерована таблиця"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def load_input(content, mode, tmp_path, filename="generated.docx"):
    if mode == "bytes":
        return load_document_bytes(content, filename=filename)
    path = tmp_path / filename
    path.write_bytes(content)
    return load_document(path)


def rewrite_package(content, replacements=None, omitted=()):
    replacements = replacements or {}
    output = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(output, "w") as target:
        for member in source.infolist():
            if member.filename not in omitted:
                target.writestr(
                    member, replacements.get(member.filename, source.read(member.filename))
                )
    return output.getvalue()


def sized_docx(content, total_bytes):
    # A stored, unreferenced XML part makes an exact-size, readable Word package.
    name = "customXml/padding.xml"
    empty = BytesIO(content)
    with ZipFile(empty, "a") as package:
        package.writestr(name, b"", compress_type=ZIP_STORED)
    padding_size = total_bytes - len(empty.getvalue())
    padding = b"<padding/>" + b" " * (padding_size - len(b"<padding/>"))
    output = BytesIO(content)
    with ZipFile(output, "a") as package:
        package.writestr(name, padding, compress_type=ZIP_STORED)
    return output.getvalue()


@pytest.mark.parametrize("filename", ["generated.docx", "generated.DOCX"])
def test_loads_path_without_changing_source(docx_content, tmp_path, filename):
    source = tmp_path / filename
    source.write_bytes(docx_content)

    document = load_document(source)

    assert document.paragraphs[0].text == GENERATED_TEXT
    assert document.tables[0].cell(0, 0).text == "Згенерована таблиця"
    document.paragraphs[0].text = "Зміна лише в пам'яті"
    document.save(BytesIO())
    assert source.read_bytes() == docx_content


def test_loads_string_path(docx_content, tmp_path):
    source = tmp_path / "generated.docx"
    source.write_bytes(docx_content)

    assert load_document(str(source)).paragraphs[0].text == GENERATED_TEXT


def test_loads_named_upload_without_creating_files(docx_content, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    document = load_document_bytes(docx_content, filename="upload.DOCX")

    assert document.paragraphs[0].text == GENERATED_TEXT
    assert document.tables[0].cell(0, 0).text == "Згенерована таблиця"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("suffix", [".doc", ".pdf", ".docm", ".zip", ""])
@pytest.mark.parametrize("mode", ["path", "bytes"])
def test_rejects_other_extensions_even_with_word_content(docx_content, tmp_path, suffix, mode):
    with pytest.raises(DocumentLoadError, match=r"Підтримуються лише файли формату \.docx\."):
        load_input(docx_content, mode, tmp_path, filename="generated" + suffix)


@pytest.mark.parametrize("mode", ["path", "bytes"])
def test_accepts_exactly_twenty_megabytes(docx_content, tmp_path, mode):
    content = sized_docx(docx_content, LIMIT_BYTES)
    assert len(content) == LIMIT_BYTES

    assert load_input(content, mode, tmp_path).paragraphs[0].text == GENERATED_TEXT


@pytest.mark.parametrize("mode", ["path", "bytes"])
def test_rejects_one_byte_over_limit_before_parsing(tmp_path, mode):
    with pytest.raises(DocumentLoadError, match="Розмір файлу перевищує 20 МБ"):
        load_input(b"\0" * (LIMIT_BYTES + 1), mode, tmp_path)


@pytest.mark.parametrize(
    "damage",
    [
        "empty",
        "not_zip",
        "missing_content_types",
        "missing_main_part",
        "malformed_xml",
        "wrong_root",
        "missing_body",
        "other_office_type",
    ],
)
@pytest.mark.parametrize("mode", ["path", "bytes"])
def test_rejects_invalid_or_renamed_packages(docx_content, tmp_path, damage, mode):
    if damage == "empty":
        content = b""
    elif damage == "not_zip":
        content = b"%PDF-1.7\n"
    elif damage == "missing_content_types":
        content = rewrite_package(docx_content, omitted=("[Content_Types].xml",))
    elif damage == "missing_main_part":
        content = rewrite_package(docx_content, omitted=("word/document.xml",))
    elif damage == "malformed_xml":
        content = rewrite_package(docx_content, {"word/document.xml": b"<broken>"})
    elif damage == "wrong_root":
        xml = f'<w:other xmlns:w="{WORD_NAMESPACE}"><w:body/></w:other>'.encode()
        content = rewrite_package(docx_content, {"word/document.xml": xml})
    elif damage == "missing_body":
        xml = f'<w:document xmlns:w="{WORD_NAMESPACE}"/>'.encode()
        content = rewrite_package(docx_content, {"word/document.xml": xml})
    else:
        with ZipFile(BytesIO(docx_content)) as package:
            types = package.read("[Content_Types].xml").replace(
                b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            )
        content = rewrite_package(docx_content, {"[Content_Types].xml": types})

    with pytest.raises(DocumentLoadError, match="Не вдалося відкрити документ .docx"):
        load_input(content, mode, tmp_path)


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_io_error_does_not_disclose_source_name(tmp_path, kind, capsys, caplog):
    source = tmp_path / "synthetic-private-name.docx"
    if kind == "directory":
        source.mkdir()

    with pytest.raises(DocumentLoadError, match="Не вдалося прочитати файл") as error:
        load_document(source)

    rendered = "".join(traceback.format_exception(error.value))
    assert source.name not in rendered
    assert str(source) not in rendered
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert caplog.records == []


def test_parser_error_does_not_disclose_input(docx_content, tmp_path, capsys, caplog):
    private_marker = "SYNTHETIC_PRIVATE_IDENTIFIER"
    private_filename = "synthetic-private-name.docx"
    xml = f'<w:document xmlns:w="{WORD_NAMESPACE}"><{private_marker}>'.encode()
    content = rewrite_package(docx_content, {"word/document.xml": xml})

    with pytest.raises(DocumentLoadError) as error:
        load_input(content, "path", tmp_path, filename=private_filename)

    rendered = "".join(traceback.format_exception(error.value))
    assert private_marker not in rendered
    assert private_filename not in rendered
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert caplog.records == []
