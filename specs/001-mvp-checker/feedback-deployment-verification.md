# Feedback deployment: ordinary text and pitch demo

User explicitly approved committing and pushing the reviewed T009a and
T018–T020 changes on 2026-11-17. Target: existing public repository
`Alkaness/oformleno`, branch `001-mvp-checker`, and its existing
[Streamlit app](https://oformleno.streamlit.app/). No other publication is in scope.

**Source published; hosted scenario verified after the user's reboot at
20:48 UTC on 2026-11-17.** The technical evidence for the stage-3 checkpoint
is complete. User confirmation of that checkpoint remains separate; T021–T023
have not started.

## Before publication

The local and remote branch heads matched after fetch. Source/documentation
review found no prohibited artifact paths or detected credential patterns.
Generated DOCX, video, PDFs, browser artifacts and private intake remain ignored.
Existing dependencies, locks, guideline YAML and source quotes are unchanged.

Local evidence: **872 pytest tests passed**, Ruff and formatting passed, both
JavaScript files pass syntax checks, document guard and whitespace pass.
Independent correctness reviews found no remaining code issue. The generic UI
gate remains **OPEN 25**, with all limitations in
[ordinary-text-mode-verification.md](ordinary-text-mode-verification.md).
Local checks are not a GitHub CI or hosted verification claim.

## Expected hosted checks

Use only the generated [T018 input](demo-script.md), with a fresh anonymous
browser session. Confirm the ordinary-text mode is the default, then upload the
actual DOCX and observe **10 errors / 9 fixable / 7 manual**. Open the corrected
report, observe **1 R08 error / 0 fixable / 7 manual**, click and save the real
download, independently reopen and check the DOCX, and verify original bytes,
text and non-main ZIP-part preservation. Clear the result and check that the
old Blob URL is revoked and ordinary mode is restored.

## Pushed source and CI

Source commit [`384c52a`](https://github.com/Alkaness/oformleno/commit/384c52a42d9a404e71cedadaddcf4dfdc76b41db)
was committed and pushed to `001-mvp-checker`. The mandatory commit hook passed
the document guard, Ruff, 89-file formatting and all **872 tests**.
[GitHub CI](https://github.com/Alkaness/oformleno/actions/runs/44172072703)
completed successfully for that exact full SHA at 20:43:37 UTC on 2026-11-17:
locked installation, document guard, Ruff, formatting and pytest all passed.
No generated document, screenshot, video or private artifact was committed.

## First hosted check: upload rejected

A fresh anonymous browser at 20:42:43 UTC loaded the updated Ukrainian mode
control: `ordinary` selected, with both `ordinary` and `styles` options. The
real generated DOCX upload did **not** produce a report. The visible error was
«Не вдалося прочитати завантаження. Оберіть файл ще раз.»; the verification
timed out waiting for the initial report. This is a hosted **FAIL**, not a pass.

The client asset update combined with rejection of the new event is consistent
with an old imported Python handler remaining cached, but the server's process
state was not inspected directly. The app sets `server.fileWatcherType="none"`.
Streamlit's [reboot guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app)
explains that rebooting clears app memory and can force a fresh build for files
the host does not monitor. Plugin discovery found no usable control for
restarting this existing Community Cloud app; Deepnote does not manage it.
The user was asked to reboot from their signed-in Streamlit workspace, after
which the full hosted scenario must be repeated.

Ignored evidence: `tmp/t009a-hosted/before-reboot/hosted-browser-evidence.json`,
the upload/failure screenshots, and `github-ci-source.json` in the parent folder.
The failed browser/profile were closed and removed. That run remains a failed
attempt and is not included in the passing evidence below.

## After the user-confirmed reboot: PASS

The user confirmed finishing the reboot. A new anonymous browser session began
at **20:48:12 UTC** and completed the real public T018 scenario without a runtime
or workflow error. No product code changed between the failed and passing run.
Reboot resolved the observed deployment issue; the cached-handler explanation
remains an inference rather than a direct inspection of server memory.

| Check | Observed result |
| --- | --- |
| Public access | Ukrainian checker opens without sign-in |
| Default and choices | Ordinary mode selected; ordinary/styles options present |
| Real upload | 10 errors, 9 fixable, 0 warnings, 7 manual |
| Ordinary-text evidence | R03, R04, R05 and selected-mode explanation present |
| Corrected HTML | R08 only: 1 error, 0 fixable, 0 warnings, 7 manual |
| Actual download click | Browser saved DOCX; saved bytes equal offered Blob |
| Independent reopened check | R08 only, 7 manual; expected values match |
| Preservation | Original SHA unchanged, all text and non-main ZIP parts preserved |
| Reset | Upload restored, old Blob URL fails to fetch, ordinary default restored |
| Narrow viewport | 390px upload-control presence captured; no mobile end-to-end claim |

Generated input SHA-256:
`e9fd9819a3b5c529e3907f44216878063962f41a7eb31bacef98c750176d5b9d`.
Actually downloaded output SHA-256:
`a3272830040c3080bbb160e5f820aeabd5aa400b98867b0ce5d99c884501dcdb`.
The output hash also matches the independently prepared local T018 copy.

Ignored final evidence is `tmp/t009a-hosted/hosted-browser-evidence.json`,
the clicked download and upload/report/corrected/narrow screenshots. Desktop
report and corrected-copy screenshots were visually inspected. All QA browsers
and their owned temporary profiles are closed/removed. No student work was read
or uploaded, no Word validation or independent-accuracy result is asserted,
and no account/sharing/dependency/YAML changes were needed.

README now names the required **workspace → app menu → Reboot** operation after
source synchronization. Merely seeing a new client control is insufficient
deployment evidence; repeat the real upload/download check. The earlier UI gate
limitations remain unchanged. Follow-up publication records these results only;
the runtime remains the verified source commit above.

The public UI does not expose a server-side Git SHA. The hosted result is
associated with the pushed deployment branch and observed new mode behavior,
not a direct inspection of the host's checkout or process. Independent read-only
review of the JSON, verifier, source CI and final documentation found no material
evidence gap. The existing mobile and UI-gate limitations remain explicit.
