---
plan: 00-01
phase: 00-pre-migration-cleanup
status: complete
tasks_completed: 2
tasks_total: 2
commits:
  - d8868b6
  - 4f451b0
key-files:
  modified:
    - pyproject.toml
    - factorio_mod_manager/core/downloader.py
    - factorio_mod_manager/core/portal.py
---

# Plan 00-01 Summary: Remove Dead Selenium Dependency and Auth Session Setup

## What Was Built

Cleaned up two dead code paths that existed in the project prior to Qt migration:

1. **Removed `selenium = "^4.25.0"` from `pyproject.toml`** — the selenium package was declared as a dependency but was never imported or used anywhere in the application code. Removing it eliminates the transitive WebDriver dependency chain and reduces attack surface.

2. **Removed dead credential auth session setup from `ModDownloader` and `FactorioPortalAPI`** — both `__init__` methods contained `if username and token: self.session.auth = (username, token)` blocks that attached HTTP Basic Auth credentials to a `requests.Session`. However, all portal HTTP calls use public endpoints and the auth header was never exercised by any request. The session itself is retained for real API calls.

## Verification Results

- `PASS: selenium removed` — confirmed via tomllib parse of pyproject.toml
- `PASS: factorio_mod_manager/core/downloader.py` — no `self.session.auth`, session retained
- `PASS: factorio_mod_manager/core/portal.py` — no `self.session.auth`, session retained
- Both files compile cleanly with `py_compile`

## Self-Check: PASSED

All acceptance criteria met:
- pyproject.toml does not contain selenium in dependencies
- FactorioModManager.spec unchanged (already had selenium in excludes)
- Neither core module contains `self.session.auth`
- Both retain `requests.Session()` construction
- Both accept `username`/`token` constructor parameters
- Both compile without errors
