# Feedback deployment: ordinary text and pitch demo

User explicitly approved committing and pushing the reviewed T009a and
T018–T020 changes on 2026-11-17. Target: existing public repository
`Alkaness/oformleno`, branch `001-mvp-checker`, and its existing
[Streamlit app](https://oformleno.streamlit.app/). No other publication is in scope.

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

Source commit, exact-revision GitHub CI and the actual hosted result are pending
at this preparation point. The previous T017 check does not prove this scenario
passes. The stage-3 checkpoint remains unconfirmed until evidence is recorded
and user confirms it. T021–T023 are not started by publication approval.
