# Research Evidence Workbench — Verification & Validation Protocol

Last verified: none — bootstrap only; no Verified release claim.

Use this procedure for the existing application and the private workbench as its tickets land. The current code is Python 3.13/FastAPI with static HTML/JavaScript/CSS, SQLite and Docker. Treat the SRS as intended pilot behavior; do not mark unimplemented planned behavior conformant.

See [bugs.md](bugs.md), [features.md](features.md), [CHANGELOG.md](CHANGELOG.md), [README.md](README.md), [SRS](docs/SRS.md), and [UI plan](docs/UI_OVERHAUL.md).

## How to use this file

1. Run every applicable stage locally; do not substitute CI results.
2. Keep run reports, logs, backups, and local state under ignored `.vv/`; keep dated run history out of this file.
3. Use the existing trackers to deduplicate failures/gaps. Do not file planned workbench scope as a regression in the legacy application.
4. Record unavailable stages explicitly. Only a full successful protocol run permits a Verified entry and migration of completed tickets.
5. Keep this file below 30 KB. Replace only the current baseline and Last verified on subsequent green runs; append history to CHANGELOG.

## Roles and abbreviations

Owner: the sole pilot user/operator. SUT: the exact checkout/image being verified. Fixture: clearly labeled generated non-confidential demonstration material. Baseline: recorded test inventory, not a release verdict.

## Verification data

| id | data | needed by | restore | depends on | probe |
|---|---|---|---|---|---|
| D1 | Legacy local demonstration reports | Existing browser smoke | `python scripts/seed_demo.py .vv/demo.db` against a new isolated path | Dependencies installed; `.vv/` exists | `DATABASE_PATH=.vv/demo.db`; GET `/api/videos` shows demo reports |
| D2 | Isolated unit/service/integration records | Automated tests | Existing pytest fixtures in `tests/conftest.py` | Temporary directory | Test database fixtures initialize and clean up |
| D3 | Private owner/documents/claims/evidence/reports | Workbench tickets once implemented | Use ticket-owned fixture/seed paths, then add exact commands here | Corresponding feature shipped | Authenticated supplied-material journey; no real user/source material |

Do not invent a D3 seed command before its implementation exists. Do not seed or wipe the configured owner database.

## Stage 0 — Pre-flight and isolated fresh stack

- [ ] Record `git rev-parse HEAD`, `git status --short`, prior Verified SHA, `python --version`, `python -m uvicorn --version`, `python -m playwright --version`, and `docker version`.
- [ ] Inventory local processes/containers/ports and required verification data. Stop only the test-owned process/container created for this run. Never run an invented Compose teardown or remove an owner volume.
- [ ] Back up any explicitly authorized verification state to `.vv/backups/` before a destructive reset; obtain authorization for a named target if existing data would be removed.
- [ ] Create a new isolated fixture directory/database and restore D1/D2. Do not reset `data/factchecker.db`.
- [ ] Build the exact checkout with `docker build -t youtube-fact-checker:verify .`; record the image ID and SHA used. Exclude uncommitted runtime changes or explicitly record them as a non-release working-tree check.
- [ ] Start a test-only container on loopback with dummy provider credentials and an isolated database; or record the precise reason a built-artifact run is unavailable. Do not pass the production `.env` to fixture-only smoke.
- [ ] Probe `/api/health` and `/openapi.json`; confirm expected process/contract version. Do not treat liveness as live research capability. Prove runtime source identity from the recorded image/build inputs before claiming SHA verification.

## Stage 1 — Static and scope checks

- [ ] Run `ruff check backend tests` with the installed virtual environment.
- [ ] Check requirement IDs, local document links, ticket dependencies and relevant data/API changes against the SRS and contracts.
- [ ] Inspect changes for secrets, raw source/query logging, untrusted HTML rendering, unsupported provider-price fallbacks and unbounded paid retries.
- [ ] Check migrations, provider policies, authentication boundaries and resource bounds for the shipped batch. Keep workbench providers disabled until actual intended-use rights are established.

## Stage 2 — Automated tests

Use the same selectors as CI. On Windows activate `.venv/Scripts/Activate.ps1`; on Unix source `.venv/bin/activate`. Use a test-owned temporary root if the system temp directory is blocked; record that environment-only variation.

| Layer | Runner | Current collected count | CI command |
|---|---|---:|---|
| Unit | pytest | 174 | `pytest tests/unit tests/services tests/integration` (combined job) |
| Services | pytest | 76 | Same combined job |
| Integration | pytest | 68 | Same combined job |
| Browser | pytest-playwright / Chromium | 16 | `pytest -m e2e tests/e2e` |

- [ ] Recollect with `pytest --collect-only -q tests/unit tests/services tests/integration` and `pytest --collect-only -q -m e2e tests/e2e`; update counts only from runner output.
- [ ] Run `pytest tests/unit tests/services tests/integration` and `pytest -m e2e tests/e2e` after Chromium is installed with `python -m playwright install chromium` if absent. Do not interpret deselected/skipped/zero-executed layers as passed.
- [ ] Require a proving test for each shipped ticket and inspect uncovered acceptance criteria.
- [ ] Run new/affected tests twice when validating implementation; record any flip in the tracker.
- [ ] Record that no coverage instrumentation or performance harness is currently configured; do not invent coverage percentages or thresholds.

## Stage 3 — Functional walkthrough

- [ ] Exercise existing applicable pages/API with isolated fixture reports; retain tests for the legacy surface while the private mode is introduced.
- [ ] Drive the private supplied-material journey against the fresh build after its tickets land: sign-in, create/import/preview, extract, correct/select, research, compare, review, export, delete.
- [ ] Use T3 collaborative preview for the manual GUI walkthrough when available. Check keyboard operation, focus, responsive layouts, themes, original-source alignment and all relevant error/empty/partial states.
- [ ] Compare the selected report revision, review state, citations and omissions in Markdown and JSON downloads.
- [ ] Record unimplemented/gated flows as blocked by their existing feature/decision IDs. Do not silently fall back to anonymous video processing as proof of the workbench.

## Stage 4 — Adversarial, retention and recovery

- [ ] Test no-session, expired/revoked/tampered session and CSRF paths across every private page/API/file/export. Confirm pilot mode blocks legacy anonymous content routes.
- [ ] Test oversized bytes/words, invalid UTF-8, malformed cues, disallowed formats, markup injection and source/evidence prompt injection using non-sensitive fixtures.
- [ ] Test simultaneous admission, one executor, idempotency, unknown pricing, budget exhaustion, bounded paid retry behavior and interrupted/restarted jobs.
- [ ] Test deletion while a provider call is in flight, late write fencing, expiry between read/export/execute, physical application-storage cleanup and content-free usage retention.
- [ ] Verify any approved restore path cannot reintroduce expired/deleted content. Do not invent backup automation for a no-automatic-backup pilot.
- [ ] Apply any new schema to a copy of the prior supported database and boot successfully. Do not automatically import historical scraped content.
- [ ] Measure duration, memory/input size, actual billable categories and researcher time for representative work; compare only against explicitly approved thresholds.

## Stage 5 — Hard product constraints

- [ ] Map the shipped batch to all applicable SRS Must requirements, UI criteria and contract invariants; attach actual evidence.
- [ ] Confirm original/proposed claim separation and source passage/cue accuracy; a matching snippet is not proof of contextual support.
- [ ] Check actual provider entitlements for processing/storage/export and correct source attribution. Use separately authorized real-provider trials; fixture tests do not establish permissions, quota or runtime success.
- [ ] Reconcile measured hosting, model and search usage to the USD 25 operating envelope before release. The existing daily video budget is not proof of the new monthly total.
- [ ] Verify privacy disclosures match actual application/backup/provider/export retention. Evaluate the approved core-flow accessibility target without claiming certification from screenshots.
- [ ] Keep any unresolved launch dependencies explicit. Do not mark a ready implementation queue as a ready deployment.

## Stage 6 — Report and migrate

- [ ] Save stage results, SHA/image, environment, actual test counts, failures and limitations to `.vv/last-run.md`.
- [ ] File only new evidence-backed defects and deduplicate against tracker IDs; leave undecided product facts in the decision register.
- [ ] On a full green run, migrate only ticked pending tickets with their Implementation/Fix and Docs notes; preserve every ID/history entry.
- [ ] Append the dated Verified entry with SHA and actual evidence to `CHANGELOG.md`, and replace the current baseline/Last verified line here. Otherwise leave Verified empty.

## Appendix A — Persistent state

Use read-only SQLite inspection against an explicitly named test database. Keep owner data, provider keys, logs, and backups out of version control. Use D1/D2 fixture paths for baseline tests.

## Appendix B — Command recipes

Use the README virtual-environment instructions and actual CI test commands above. Import `tests/e2e/conftest.py` fixtures only for test-owned seeded processes; do not use dummy provider credentials against real paid research.

## Appendix C — Container and platform commands

Use `docker build -t youtube-fact-checker:verify .` for a local image. Choose an unused loopback test port and a unique container name at runtime; record them in `.vv/last-run.md`. Stop/remove only that named test container. No Compose configuration is present.

## Appendix D — Provider modes

Use existing mocks for deterministic unit/service/integration tests. Enable real workbench providers only after the policy, budget and job tickets and their actual rights/configuration gates are complete. Do not add a hidden scraper fallback.

## Appendix E — Short smoke checklist

- [ ] Liveness responds without private data.
- [ ] Private mode rejects unauthenticated content access.
- [ ] Supported supplied text imports with original source preserved.
- [ ] Claims and job state reflect actual completed work.
- [ ] Evidence and draft/review state remain distinguishable.
- [ ] Explicit exports carry the selected revision and permitted data.
- [ ] Deletion/expiry cannot be undone by a late job response.
- [ ] Budget/rights failures never appear as successful research.
