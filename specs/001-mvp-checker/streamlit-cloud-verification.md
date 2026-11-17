# T017: Streamlit Community Cloud verification

Public URL supplied by the user: https://oformleno.streamlit.app/.
The source repository remains private: `Alkaness/oformleno`, branch
`001-mvp-checker` (GitHub API verification on 2026-11-17).

## Current status

The user enabled public sharing after an anonymous browser initially reached
Streamlit's access/not-found page. A fresh anonymous browser then loaded the
real checker through Cloud's same-origin app iframe and completed the actual
upload, report and corrected-copy download. A reset cleanup defect was found
and repaired locally; the updated deployment still needs its final hosted test.
T017 remains unchecked until that test passes. T018 has not been started.

## Hosted evidence before the cleanup fix (2026-11-17)

Only a generated DOCX was uploaded. It combines the existing synthetic R08
caption case with a 20 mm left margin. No real student work was used.

| Check | Observed result |
| --- | --- |
| Anonymous access | Actual Ukrainian checker loaded without sign-in |
| Initial report | R02 and R08: 2 errors, 1 fixable, 0 warnings, 7 manual checks |
| Corrected report | 1 error, 0 fixable, 0 warnings, 7 manual checks |
| Actual download link | Clicked; saved bytes matched the offered Blob |
| Download validity | Reopened with python-docx and checked locally: only R08 remained |
| Preservation | Original hash unchanged; text and media preserved in the copy |
| Reset | Returned to upload, but the old Blob URL remained usable: FAIL |

The HTTP 200 response alone was not treated as proof of public access. The
earlier access failure and the subsequent probe's missing iframe traversal are
retained separately in ignored `tmp/t017/`; neither counts as a functional pass.

## Cleanup repair and local verification

Streamlit v2 calls the renderer again when data changes but invokes its returned
cleanup on unmount. The component now explicitly disposes the preceding render
and disposes immediately on reset. Disposal aborts a reader, clears references,
revokes the copy's URL and clears the DOM only while owning the current render.
An idempotent disposer prevents late cleanup from erasing a newer render.

The existing frontend harness now retains the same parent/root across updates
without calling platform cleanup. It checks repeat rendering, immediate URL
revocation on reset, preserved copy bytes and late cleanup of a prior render.
The foreground Taste screenshot shows `FRONTEND: PASS` in
`tmp/t017/frontend-lifecycle.png`. This is a functional regression result, not
a new visual gate pass. Existing T016 design/performance limitations remain in
[web-demo-verification.md](web-demo-verification.md).

`requirements.txt` uses editable installation (`-e .`) so subsequent source and
asset syncs use the checkout. A running app still requires restart to load code
changes. A clean Python 3.12 install confirmed editable metadata, source-backed
assets, active YAML, all 48 pinned runtime versions and no pytest/Ruff. Runtime
dependencies, both locks, rules and quotations were not changed.

Independent read-only review found no remaining blocker in the lifecycle fix,
regression harness or installation change. `sh scripts/check.sh` passed Ruff,
formatting (78 files) and 838 tests on Python 3.12.3. JavaScript syntax and
whitespace checks passed. Earlier deployment source `bac5efb` has a successful
[GitHub CI run](https://github.com/Alkaness/oformleno/actions/runs/43315359929);
that earlier CI is not evidence for this new repair revision.

## Evidence limits

The browser probe reads all four displayed counts, clicks the real download
link, compares saved bytes with the Blob, reopens/checks the downloaded DOCX,
checks text/media preservation and reset revocation. It uses a new temporary
anonymous browser profile. QA artifacts, generated DOCX and screenshots stay
ignored and are not committed.

The desktop flow is the functional scenario. A narrow screenshot/input-presence
check is not a mobile upload/download or physical-device test. This verification
does not claim Word compatibility, full EOM norm-control, an always-awake host,
the T018 pitch scenario or T020's 30-page timing.
