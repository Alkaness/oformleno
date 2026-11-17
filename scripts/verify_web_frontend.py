"""Generate an isolated browser check of the real component using synthetic DOCX.

This does not launch a browser or a service. Open the generated HTML with the
project's Taste scripts. AppTest separately exercises the actual Streamlit
callbacks; this harness checks browser FileReader, DOM and Blob behavior.
"""

import argparse
import base64
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.shared import Mm

from oformleno.web import WebState, accept_upload, reveal_copy, view_data

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures.make_fixtures import generate_fixtures  # noqa: E402

_DRIVER = r"""
const uiUrl = URL.createObjectURL(new Blob([fixture.js], {type: 'text/javascript'}));
const {default: render} = await import(uiUrl);
URL.revokeObjectURL(uiUrl);
let cleanup = () => {};
const events = [];
const mountElement = document.querySelector('#mount');
mountElement.innerHTML = fixture.html;
function mount(data) {
  // Data updates rerun the renderer without the platform calling unmount cleanup.
  cleanup = render({parentElement: mountElement, data,
    setTriggerValue: (event, value) => events.push({event, value})});
}
function assert(value, message) { if (!value) throw new Error(message); }
function choose(file) {
  const input = document.querySelector('.app-file');
  const transfer = new DataTransfer(); transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event('change', {bubbles: true}));
}
function click(text) {
  const control = Array.from(document.querySelectorAll('#oformleno-root button'))
    .find(button => button.textContent === text);
  assert(control, 'Missing named control'); control.click();
}
async function hash(bytes) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map(x => x.toString(16).padStart(2, '0')).join('');
}
try {
  mount({report: null});
  assert(document.querySelector('.app-check').disabled, 'Check enabled without file');
  choose(new File(['x'], 'generated.pdf'));
  assert(document.querySelector('.app-error').textContent.includes('лише файли'),
    'Extension validation');
  choose(new File([new Uint8Array(20 * 1024 * 1024 + 1)], 'large.docx'));
  assert(document.querySelector('.app-error').textContent.includes('перевищує'), 'Size validation');
  assert(events.length === 0, 'Invalid file transmitted');
  const bytes = Uint8Array.from(atob(fixture.source), x => x.charCodeAt(0));
  choose(new File([bytes], '<img src=x onerror=alert(1)>.docx'));
  assert(!document.querySelector('.app-selected img'), 'Filename interpreted as HTML');
  assert(!document.querySelector('.app-check').disabled, 'Valid file rejected');
  click('Перевірити документ');
  const started = Date.now();
  while (!events.length && Date.now() - started < 5000) await new Promise(r => setTimeout(r, 20));
  assert(events.length === 1 && events[0].event === 'upload', 'Upload trigger not delivered');
  assert(events[0].value.content === fixture.source, 'FileReader changed input bytes');
  assert(document.querySelector('.app-file').files.length === 0, 'File input retained source');
  assert(!document.querySelector('.app-selected').textContent, 'Filename retained after send');
  events.length = 0;
  mount(fixture.before);
  assert(document.querySelector('#findings').textContent.includes('R02'),
    'Original report missing');
  click('Переглянути виправлену копію');
  assert(events.at(-1).event === 'reveal', 'Reveal trigger not delivered');
  mount(fixture.after);
  assert(!document.querySelector('#findings').textContent.includes('R02'), 'Fixed error retained');
  assert(document.querySelector('#findings').textContent.includes('R08'), 'Residual error lost');
  assert(document.querySelector('#manual').textContent.includes('M08'), 'Manual evidence lost');
  let link = document.querySelector('a.app-download');
  assert(link && link.download === 'Виправлена_копія.docx', 'Download name/control missing');
  assert(link.compareDocumentPosition(document.querySelector('.summary a[href="#manual"]'))
    & Node.DOCUMENT_POSITION_FOLLOWING, 'Primary download placed after secondary navigation');
  const content = await (await fetch(link.href)).arrayBuffer();
  assert(await hash(content) === fixture.corrected_hash, 'Download Blob bytes differ');
  const previousUrl = link.href;
  const previousCleanup = cleanup;
  mount(fixture.after);
  previousCleanup();
  link = document.querySelector('a.app-download');
  assert(link && link.href !== previousUrl, 'Old cleanup erased the current render');
  let previousRevoked = false;
  try { await fetch(previousUrl); } catch { previousRevoked = true; }
  assert(previousRevoked, 'Data rerender retained the previous Blob');
  const repeated = await (await fetch(link.href)).arrayBuffer();
  assert(await hash(repeated) === fixture.corrected_hash, 'Repeated render changed copy');
  const oldUrl = link.href;
  click('Очистити результат');
  assert(events.at(-1).event === 'reset', 'Reset trigger not delivered');
  let revoked = false;
  try { await fetch(oldUrl); } catch { revoked = true; }
  assert(revoked, 'Reset did not immediately revoke the old download Blob');
  mount({report: null});
  assert(!document.querySelector('.app-download'), 'Stale download after reset');
  mount(fixture.after);
  document.querySelector('#qa-status').textContent = 'FRONTEND: PASS — FileReader, validation, '
    + 'text escaping, report, residual/manual evidence, Blob bytes and reset';
  document.body.dataset.qa = 'pass';
} catch (error) {
  document.querySelector('#qa-status').textContent = 'FRONTEND: FAIL — ' + error.message;
  document.body.dataset.qa = 'fail';
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="oformleno-web-qa-")) / "frontend.html"
    with tempfile.TemporaryDirectory(prefix="oformleno-web-fixtures-") as folder:
        paths = generate_fixtures(Path(folder))
        document = Document(paths["bad_r08"])
        document.sections[0].left_margin = Mm(20)
        combined = Path(folder) / "combined.docx"
        document.save(combined)
        source = combined.read_bytes()
        state = WebState()
        accept_upload(
            state, {"name": "generated.docx", "content": base64.b64encode(source).decode()}
        )
        assert state.result and state.result.before.summary.errors == 2
        before = view_data(state)
        reveal_copy(state)
        after = view_data(state)
        assert state.result.after.summary.errors == 1 and state.result.after.summary.manual == 7
        assets = ROOT / "src/oformleno/web_assets"
        fixture = {
            "html": (assets / "interface.html").read_text(),
            "js": (assets / "interface.js").read_text(),
            "source": base64.b64encode(source).decode(),
            "before": before,
            "after": after,
            "corrected_hash": hashlib.sha256(state.result.corrected).hexdigest(),
        }
        encoded = json.dumps(fixture, ensure_ascii=False).replace("</", "<\\/")
        page = (
            '<!doctype html><html lang="uk"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Oformleno synthetic frontend verification</title><style>"
            + (assets / "interface.css").read_text()
            + '</style></head><body><output id="qa-status">FRONTEND: RUNNING</output>'
            '<div id="mount"></div><script type="module">const fixture = '
            + encoded
            + ";\n"
            + _DRIVER
            + "</script></body></html>"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
    print(f"Synthetic frontend browser check: {output}")


if __name__ == "__main__":
    main()
