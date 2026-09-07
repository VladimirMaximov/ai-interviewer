# Quickstart Validation: Asynchronous AI Interview

Use only synthetic candidates and generated audio fixtures.

1. Create an approved six-question template and a valid invitation.
2. Open it in a modern browser; verify recording notice, affirmative consent, avatar speech, text
   alternative, recording, replace-before-submit, and successful submission.
3. Confirm one answer, close the browser, reopen the invitation, and verify saved progress.
4. Try malformed, expired, revoked, and submitted links; confirm no interview or candidate data is
   revealed.
5. Simulate transcription failure; confirm audio remains available and the reviewer sees failed or
   pending status rather than invented text.
6. Check assigned reviewer access, unassigned reviewer denial, evidence-to-transcript traceability,
   and separate AI/recruiter/hiring-manager decisions.

Run the repository quality gate:

```bash
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q tools/product-research/product_engineering
```
