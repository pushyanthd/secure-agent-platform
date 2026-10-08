# Operator UI verification — September 23, 2026

The authenticated browser console passed nine automated Chrome scenarios against
a real loopback API and separately invoked workers. Responses are authored
fixtures, tools use the trusted in-process backend, and review clicks are
automated. **This bundle contains zero fresh model trials.**

The passing run took 31.1 seconds. The Python suite passed 267 tests; Python lint,
formatting, strict mypy, TypeScript, frontend formatting, and production build
also passed. A wheel smoke verified that the installed package serves the UI,
keeps API authentication, and excludes local credentials/artifacts. CI now runs
the browser suite separately; this bundle reports the local run, not a remote CI result.

See [checks.json](checks.json) for the checked behaviors and
[the runbook](../../operator-ui.md) for reproduction.

- [Exact-action approval, desktop](approval-desktop.png)
- [Completed execution, desktop](completed-desktop.png)
- [Hostile text displayed literally, 390-pixel mobile viewport](approval-mobile.png)

The mobile screenshot deliberately includes synthetic HTML/script text in an
action argument. The browser check confirms that no injected element or script
was executed and that the document fits the viewport.

The first browser attempt passed eight scenarios; the stale-resource test helper
incorrectly addressed a nonexistent `projects` table. It was corrected to update
the version in `resources.payload`. All nine scenarios then passed. No application
security assertion was relaxed. A prior sandboxed attempt could not bind the
loopback listener and did not execute browser scenarios.

Screenshots show synthetic state only, with no bearer token or approval nonce.
`checksums.json` covers the PNGs and verification JSON; it detects changes but
does not authenticate evidence against the machine owner. Full local test state
and server logs remain in ignored `artifacts/browser-tests/`; temporary token
files were deleted by test teardown. Human usability, fresh-model behavior,
hard worker isolation, and the held-out release gate remain separate evidence.
