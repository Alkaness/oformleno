---
name: oformleno-rule
description: Implement or fix an Oformleno formatting rule R01–R10 and its pytest coverage on .docx files. Use for rule work, not repository setup or design.
---

# DOCX formatting rules

Work only on rules included in the currently authorized task. Read `AGENTS.md`,
the relevant acceptance criterion in `specs/001-mvp-checker/spec.md`, the technical
note in `plan.md`, and the rule in `rulesets/lpnu-afm-kontrolna-2025.yaml`.

Keep each rule in its own `src/oformleno/rules/rNN_*.py` file, with tests in
`tests/test_rNN_*.py`. Read parameters and source quotations from the ruleset
instead of duplicating them in code. Preserve the existing `DocumentModel` and
`Finding` interfaces. If they do not exist yet, check task dependencies first.

Generate `.docx` fixtures with `python-docx` in `tmp_path`. Verify inheritance
and unusual OpenXML through an actual save and reopen, rather than mocking the
entire document model. Do not commit generated documents.

Cover a valid example, the specified acceptance failure, and relevant boundaries
such as measurement tolerance or inherited values. Choose cases according to
the particular rule's risks. `None` can indicate inheritance; do not treat it as
a formatting violation. Return `manual` when reliable evaluation is impossible.

If autofix is part of the authorized task, verify the original remains unchanged
byte for byte, recheck the fixed copy, and verify content preservation. Do not
add autofix to rules whose requirements exclude it.

Run affected rule tests and relevant integration tests. Before finishing, run
`sh scripts/check.sh` and report observed results and limitations.
