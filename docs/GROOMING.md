# Groomed backlog — private research workbench and UI overhaul

Status: **approved and filed** on 2026-10-14. The stakeholder approved all 18 feature tickets, one pricing bug, the UI plan and its engineering defaults. The project cycle files are bootstrapped. Implementation has not started.

Authoritative working tickets: [features.md](../features.md) and [bugs.md](../bugs.md). Specifications: [SRS](SRS.md), [Data Contracts](DATA_CONTRACTS.md), [Architecture](ARCHITECTURE.md), [approved UI overhaul](UI_OVERHAUL.md). Supporting research: [Product feasibility](PRODUCT_FEASIBILITY.md), [Provider feasibility](EVIDENCE_PROVIDER_FEASIBILITY.md).

## 1. Readiness and authorization

**Ready to begin:** `/implement FEAT-1792003576`. The pricing bug [BUG-1792003575](../bugs.md#bug-1792003575-correct-sonnet-55-cache-read-pricing-and-reject-unrated-usage) is also independent. Other feature work follows the dependencies below. Ticket filing is not authorization to start implementation in this planning session, merge, purchase services or deploy.

The approved defaults are one owner passphrase with revocable server sessions, a 1 MiB UTF-8 import bound alongside the approved word/claim limits, fixed creation-based retention, no automatic content backups initially, and a core-flow WCAG 2.2 AA target. SRS TBD-007/TBD-008 are resolved decisions; TBD-005/TBD-006 are partially resolved.

Live provider use remains gated on verified intended-use permissions, actual prices and operational measurements. Baseline tests/builds do not establish workbench implementation or live research capability. A ready initial queue is separate from a launch-ready product.

## 2. Stack profile and baseline

- Source checkout: `feat/v2-upgrade` at `728ff5b59e8e50f486af19fbcbaf3013deb512c3`; this was the inspected runtime baseline before the planning commits; no application code changed during grooming.
- Deliverable: Python 3.13 / FastAPI service with plain HTML/JavaScript/CSS, SQLite/aiosqlite and Docker. No Node build or frontend package manager.
- Build: `docker build -t youtube-fact-checker .` derives from the existing Dockerfile; Docker Engine 29.8.2 built the existing application successfully; isolated smoke used no owner database or live provider keys.
- Run: `uvicorn backend.main:app --reload`; container starts Uvicorn on `PORT` (8000 default). Health route `/api/health` is liveness only.
- CI: GitHub Actions runs lint, non-browser tests, then Playwright Chromium. No deployment job is present in the workflow.
- External providers: Anthropic SDK behind llm service; Brave/Google through httpx search service; current YouTube ingestion uses yt-dlp/transcript library but is outside the new supplied-material pilot.
- Auth: no current owner-session boundary found; it is planned work, not an existing capability.
- State: local SQLite path is configurable; `scripts/seed_demo.py` seeds an explicitly supplied demo path. No Compose reset command exists. Never delete or reseed the owner database to run verification.
- Perf: no dedicated performance harness or approved numeric latency target found; SRS capacity/concurrency limits apply; empirical thresholds remain open.
- Version source: `backend/main.py` declares FastAPI application version `2.0.0`; no Git release tag or packaging version was found. Ticket bumps describe future change impact; no release is cut here.
- Area tags: `api`, `ui`, `services`, `storage`, `security`, `tests`, `docs`.

| Layer | Native collection count | CI/local command | Prerequisites / limits |
|---|---:|---|---|
| Static | n/a | `ruff check backend tests` | Existing installed ruff; observed PASS |
| Unit | 174 | `pytest tests/unit tests/services tests/integration` | Combined CI job; temporary fixtures/mocked services |
| Service | 76 | Same combined CI command | Existing fixtures; no live provider proof |
| Integration | 68 | Same combined CI command | Isolated temporary SQLite; includes existing public API tests |
| Browser E2E | 16 | `pytest -m e2e tests/e2e` | Installed Chromium; seeded server; YouTube browser requests blocked |

Counts were collected through pytest, not guessed from filenames. The existing baseline was executed: 318 non-browser tests and all 16 browser tests passed; lint passed. The Docker image built successfully, and isolated dummy-key container health/OpenAPI/homepage smoke returned HTTP 200. These baseline checks do not establish workbench implementation or live-provider permissions. Bootstrap baseline run output, actual command availability, and failed/unavailable prerequisites are recorded separately; no Verified entry may be written without a full protocol run.

## 3. Filed ticket index

| Filed ID | Type | Title | Priority / severity | Bump | Depends on | Status |
|---|---|---|---|---|---|---|
| [FEAT-1792003576](../features.md#feat-1792003576-add-owner-authentication-and-a-fail-closed-private-pilot-boundary) | Feature | Add owner authentication and a fail-closed private pilot boundary | high | minor | None | open |
| [FEAT-1792003577](../features.md#feat-1792003577-create-private-investigations-with-immutable-source-provenance) | Feature | Create private investigations with immutable source provenance | high | minor | FEAT-1792003576 | open |
| [FEAT-1792003578](../features.md#feat-1792003578-build-the-private-workspace-shell-and-investigations-dashboard) | Feature | Build the private workspace shell and investigations dashboard | high | minor | FEAT-1792003576, FEAT-1792003577 | open |
| [FEAT-1792003579](../features.md#feat-1792003579-import-and-preview-authorized-txt-srt-vtt-and-pasted-material) | Feature | Import and preview authorized TXT, SRT, VTT and pasted material | high | minor | FEAT-1792003577, FEAT-1792003578 | open |
| [FEAT-1792003580](../features.md#feat-1792003580-gate-model-and-evidence-integrations-on-recorded-use-policies) | Feature | Gate model and evidence integrations on recorded use policies | high | minor | FEAT-1792003577 | open |
| [FEAT-1792003581](../features.md#feat-1792003581-enforce-monthly-research-reservations-and-content-free-usage-accounting) | Feature | Enforce monthly research reservations and content-free usage accounting | high | minor | FEAT-1792003577, FEAT-1792003580 | open |
| [FEAT-1792003582](../features.md#feat-1792003582-run-durable-extraction-and-research-jobs-with-one-fenced-executor) | Feature | Run durable extraction and research jobs with one fenced executor | high | minor | FEAT-1792003581 | open |
| [FEAT-1792003583](../features.md#feat-1792003583-extract-locatable-candidate-claims-from-supplied-documents) | Feature | Extract locatable candidate claims from supplied documents | high | minor | FEAT-1792003579, FEAT-1792003582 | open |
| [FEAT-1792003584](../features.md#feat-1792003584-review-correct-and-freeze-a-bounded-claim-selection) | Feature | Review, correct and freeze a bounded claim selection | high | minor | FEAT-1792003583 | open |
| [FEAT-1792003585](../features.md#feat-1792003585-retrieve-policy-permitted-supporting-and-conflicting-evidence) | Feature | Retrieve policy-permitted supporting and conflicting evidence | high | minor | FEAT-1792003584, FEAT-1792003580, FEAT-1792003581 | open |
| [FEAT-1792003586](../features.md#feat-1792003586-generate-evidence-linked-draft-assessments-with-validated-citations) | Feature | Generate evidence-linked draft assessments with validated citations | high | minor | FEAT-1792003585 | open |
| [FEAT-1792003587](../features.md#feat-1792003587-build-the-source-and-evidence-comparison-workbench) | Feature | Build the source and evidence comparison workbench | high | minor | FEAT-1792003586, FEAT-1792003578 | open |
| [FEAT-1792003588](../features.md#feat-1792003588-edit-report-revisions-and-explicitly-record-researcher-review) | Feature | Edit report revisions and explicitly record researcher review | high | minor | FEAT-1792003587 | open |
| [FEAT-1792003589](../features.md#feat-1792003589-download-policy-filtered-markdown-and-json-report-exports) | Feature | Download policy-filtered Markdown and JSON report exports | high | minor | FEAT-1792003588, FEAT-1792003580 | open |
| [FEAT-1792003590](../features.md#feat-1792003590-delete-investigations-immediately-while-fencing-active-paid-work) | Feature | Delete investigations immediately while fencing active paid work | high | minor | FEAT-1792003589, FEAT-1792003582, FEAT-1792003581 | open |
| [FEAT-1792003591](../features.md#feat-1792003591-expire-investigations-and-enforce-cleanup-across-restart-and-reads) | Feature | Expire investigations and enforce cleanup across restart and reads | high | minor | FEAT-1792003590 | open |
| [FEAT-1792003592](../features.md#feat-1792003592-show-truthful-progress-research-availability-and-operating-usage) | Feature | Show truthful progress, research availability and operating usage | high | minor | FEAT-1792003582, FEAT-1792003581, FEAT-1792003578, FEAT-1792003590 | open |
| [FEAT-1792003593](../features.md#feat-1792003593-complete-keyboard-responsive-and-research-quality-pilot-acceptance) | Feature | Complete keyboard, responsive and research-quality pilot acceptance | med | minor | FEAT-1792003591, FEAT-1792003592, FEAT-1792003589 | open |
| [BUG-1792003575](../bugs.md#bug-1792003575-correct-sonnet-55-cache-read-pricing-and-reject-unrated-usage) | Bug | Correct Sonnet 5.5 cache-read pricing and reject unrated usage | med | patch | None | open |

No duplicates were dropped: no tracker/archive existed before bootstrap, and approved ticket intents are distinct. All filed IDs were minted from actual epoch seconds during filing; provisional proposal IDs were not reused as permanent ticket IDs.

Every feature adds opt-in private-workbench behavior. No ticket silently retires a released anonymous public contract. A later default-mode cutover or public-contract removal requires a separately planned **major** change; no major release is cut here.

## 4. Recommended implementation order

1. [FEAT-1792003576](../features.md#feat-1792003576-add-owner-authentication-and-a-fail-closed-private-pilot-boundary) — owner access and fail-closed private mode; then [FEAT-1792003577](../features.md#feat-1792003577-create-private-investigations-with-immutable-source-provenance) — private investigation/source foundation. Fix [BUG-1792003575](../bugs.md#bug-1792003575-correct-sonnet-55-cache-read-pricing-and-reject-unrated-usage) independently.

2. [FEAT-1792003578](../features.md#feat-1792003578-build-the-private-workspace-shell-and-investigations-dashboard) and [FEAT-1792003579](../features.md#feat-1792003579-import-and-preview-authorized-txt-srt-vtt-and-pasted-material) — workspace/dashboard and supplied-material import. After the data foundation, [FEAT-1792003580](../features.md#feat-1792003580-gate-model-and-evidence-integrations-on-recorded-use-policies) and [FEAT-1792003581](../features.md#feat-1792003581-enforce-monthly-research-reservations-and-content-free-usage-accounting) implement provider and spending controls.

3. [FEAT-1792003582](../features.md#feat-1792003582-run-durable-extraction-and-research-jobs-with-one-fenced-executor), [FEAT-1792003583](../features.md#feat-1792003583-extract-locatable-candidate-claims-from-supplied-documents), then [FEAT-1792003584](../features.md#feat-1792003584-review-correct-and-freeze-a-bounded-claim-selection) — durable paid work, source-grounded candidates and researcher-selected claims.

4. [FEAT-1792003585](../features.md#feat-1792003585-retrieve-policy-permitted-supporting-and-conflicting-evidence), [FEAT-1792003586](../features.md#feat-1792003586-generate-evidence-linked-draft-assessments-with-validated-citations), then [FEAT-1792003587](../features.md#feat-1792003587-build-the-source-and-evidence-comparison-workbench) — policy-permitted evidence, draft assessment and comparison UI. Actual live provider enablement requires the unresolved factual gates.

5. [FEAT-1792003588](../features.md#feat-1792003588-edit-report-revisions-and-explicitly-record-researcher-review), [FEAT-1792003589](../features.md#feat-1792003589-download-policy-filtered-markdown-and-json-report-exports), [FEAT-1792003590](../features.md#feat-1792003590-delete-investigations-immediately-while-fencing-active-paid-work), [FEAT-1792003591](../features.md#feat-1792003591-expire-investigations-and-enforce-cleanup-across-restart-and-reads), and [FEAT-1792003592](../features.md#feat-1792003592-show-truthful-progress-research-availability-and-operating-usage) — reviewed revisions, private exports, lifecycle and usage/recovery UI.

6. [FEAT-1792003593](../features.md#feat-1792003593-complete-keyboard-responsive-and-research-quality-pilot-acceptance) — core-flow accessibility, responsive behavior and representative evaluation evidence.

The filed feature order is a valid topological order. This is sequencing, not an instruction to spawn agents or create concurrent writers. A cohesive batch needs separate implementation authorization.

## 5. Decision register and factual gates

| Issue | Current disposition | Effect |
|---|---|---|
| TBD-001 | Open: actual provider entitlements for inference, saved material, derived reports and export; applicable prices/limits | Build policy controls offline; do not enable unverified live research |
| TBD-002 | Open: actual hosting/job consumption and report volume | USD 25 design envelope remains; no guaranteed report count or final external bill |
| TBD-003 | Open: measured quality, time saved, latency and availability targets | Deterministic integrity gates apply; empirical release thresholds are not invented |
| TBD-004 | Open: representative topics/languages and evaluation corpus | Use labeled authorized fixtures; do not promise broad coverage |
| TBD-005 | Partially resolved: 1 MiB UTF-8 bound accepted; token/markup/memory behavior to verify | Import implementation can proceed; prove bounded behavior before paid deployment |
| TBD-006 | Partially resolved: fixed clock, no automatic content backups and revocable session policy accepted | Verify physical purge/host/provider-copy limits and final accounting purge window |
| TBD-007 | Resolved: approved browser/layout matrix and core-flow WCAG 2.2 AA target | Implement and verify; no current certification or conformance claim |
| TBD-008 | Resolved: Argon2 owner passphrase and opaque revocable SQLite sessions | First ticket has a concrete mechanism; verify/pin dependency at implementation |

There are six open or partially open issues. They do not prevent the independent initial auth/data/UI implementation queue; they do gate affected live workflows or final release. No contract/account fact was approved into existence by the backlog decision.

## 6. Cycle-file bootstrap result

- Created [bugs.md](../bugs.md), [features.md](../features.md), [CHANGELOG.md](../CHANGELOG.md), and [VERIFICATION.md](../VERIFICATION.md) in protocol bootstrap order; updated [README.md](../README.md) last. All 19 tickets are open; archives and Verified are empty.
- Added union-merge attributes for feature/bug/changelog files, ignored `.vv/` local reports, and added [AGENTS.md](../AGENTS.md) as the concise shared cycle pointer. The repository intentionally ignores personal `CLAUDE.md`.
- Preserved existing runtime code, tests, owner data, deployment and public branch behavior. No data reset, new account, purchase, merge or deployment was performed.
- Baseline evidence was recorded during planning: lint, 318 non-browser tests, 16 browser tests, Docker image build and isolated dummy-key container smoke passed. No full V&V or pilot release verdict is claimed.
- Full ticket bodies now live only in the root trackers. This document owns sequence/readiness and requirement coverage, preventing a duplicated proposed backlog from going stale.

## 7. Requirement and UI coverage

| Requirement / surface | Filed work |
|---|---|
| FR-001; NFR-005; UI-001 | [FEAT-1792003576](../features.md#feat-1792003576-add-owner-authentication-and-a-fail-closed-private-pilot-boundary) |
| FR-002; IR-001; UI-002 | [FEAT-1792003577](../features.md#feat-1792003577-create-private-investigations-with-immutable-source-provenance), [FEAT-1792003578](../features.md#feat-1792003578-build-the-private-workspace-shell-and-investigations-dashboard) |
| FR-003–FR-005; NFR-002; CON-004–CON-005; UI-003 | [FEAT-1792003579](../features.md#feat-1792003579-import-and-preview-authorized-txt-srt-vtt-and-pasted-material), [FEAT-1792003577](../features.md#feat-1792003577-create-private-investigations-with-immutable-source-provenance) |
| FR-006; UI-004 | [FEAT-1792003583](../features.md#feat-1792003583-extract-locatable-candidate-claims-from-supplied-documents) |
| FR-007; UI-004 | [FEAT-1792003584](../features.md#feat-1792003584-review-correct-and-freeze-a-bounded-claim-selection) |
| FR-008; IR-002 | [FEAT-1792003580](../features.md#feat-1792003580-gate-model-and-evidence-integrations-on-recorded-use-policies), [FEAT-1792003585](../features.md#feat-1792003585-retrieve-policy-permitted-supporting-and-conflicting-evidence) |
| FR-009–FR-010; UI-005 | [FEAT-1792003586](../features.md#feat-1792003586-generate-evidence-linked-draft-assessments-with-validated-citations), [FEAT-1792003587](../features.md#feat-1792003587-build-the-source-and-evidence-comparison-workbench) |
| FR-011–FR-012; NFR-004; UI-006 | [FEAT-1792003588](../features.md#feat-1792003588-edit-report-revisions-and-explicitly-record-researcher-review), [FEAT-1792003586](../features.md#feat-1792003586-generate-evidence-linked-draft-assessments-with-validated-citations) |
| FR-013; CON-003; UI-006 | [FEAT-1792003589](../features.md#feat-1792003589-download-policy-filtered-markdown-and-json-report-exports) |
| FR-014–FR-015; UI-008 | [FEAT-1792003590](../features.md#feat-1792003590-delete-investigations-immediately-while-fencing-active-paid-work), [FEAT-1792003591](../features.md#feat-1792003591-expire-investigations-and-enforce-cleanup-across-restart-and-reads) |
| FR-016; NFR-001; UI-007 | [FEAT-1792003582](../features.md#feat-1792003582-run-durable-extraction-and-research-jobs-with-one-fenced-executor), [FEAT-1792003592](../features.md#feat-1792003592-show-truthful-progress-research-availability-and-operating-usage) |
| FR-017–FR-018; CON-002; UI-008 | [FEAT-1792003581](../features.md#feat-1792003581-enforce-monthly-research-reservations-and-content-free-usage-accounting), [FEAT-1792003592](../features.md#feat-1792003592-show-truthful-progress-research-availability-and-operating-usage), [BUG-1792003575](../bugs.md#bug-1792003575-correct-sonnet-55-cache-read-pricing-and-reject-unrated-usage) |
| NFR-006–NFR-007 | [FEAT-1792003580](../features.md#feat-1792003580-gate-model-and-evidence-integrations-on-recorded-use-policies), [FEAT-1792003592](../features.md#feat-1792003592-show-truthful-progress-research-availability-and-operating-usage) |
| NFR-003; NFR-008; UI plan §5–§7 | [FEAT-1792003593](../features.md#feat-1792003593-complete-keyboard-responsive-and-research-quality-pilot-acceptance) |
| CON-001; UI plan §6 | [FEAT-1792003576](../features.md#feat-1792003576-add-owner-authentication-and-a-fail-closed-private-pilot-boundary), [FEAT-1792003578](../features.md#feat-1792003578-build-the-private-workspace-shell-and-investigations-dashboard), [FEAT-1792003579](../features.md#feat-1792003579-import-and-preview-authorized-txt-srt-vtt-and-pasted-material), [FEAT-1792003582](../features.md#feat-1792003582-run-durable-extraction-and-research-jobs-with-one-fenced-executor) |

## 8. Next action

Run `/implement FEAT-1792003576` to begin the first ticket when implementation is requested. Keep each ticket open until that workflow starts; do not mark any code delivered based on this planning/bootstrap commit.
