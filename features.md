# Research Evidence Workbench — Feature Tracker

## Conventions

Append new entries at the end of `## Open`; never reorder, reuse an ID, or truncate history. IDs are actual UNIX epoch seconds at filing, prefixed `FEAT-`. Area tags: api, ui, services, storage, security, tests, docs.

Each entry has an unchecked Priority line, Area, File(s), Why, Approach, Library / dependency notes, Acceptance criteria, Test plan, Out of scope, Bump, and Status. Dependencies and Execution gate distinguish implementation sequencing from external enablement facts. Paths explicitly introduced as new are proposed files, not claims that files already exist.

Priority: crit blocks a hard constraint; high delivers or unblocks the pilot core path; med improves supporting usability/verification; low is optional polish. Each Why/Execution gate states the product or risk basis. Features normally have Bump minor; breaking a released contract is major and requires explicit release planning, not an automatic version bump.

Lifecycle: `open -> in-progress -> shipped-pending-migration`. Implement one approved ticket at a time or an explicitly authorized cohesive batch. Tick only verified delivery, then add Implementation and Docs notes. Only full V&V moves completed entries to `## Shipped` and the changelog. Empty archives are intentional; no work is falsely marked shipped.

Sources: [SRS](docs/SRS.md), [UI plan](docs/UI_OVERHAUL.md), [Grooming and order](docs/GROOMING.md). Backlog and defaults approved on 2026-10-14; this files work, not implementation or deployment authorization.

---

## Open

### [FEAT-1792003576] Add owner authentication and a fail-closed private pilot boundary

- [ ] **Priority:** high
- **Area:** api, security, ui
- **File(s):** backend/main.py, backend/config.py, backend/database.py, requirements.txt; new backend/auth.py, frontend/sign-in.html, frontend/sign-in.js, tests/integration/test_owner_auth.py
- **Why:** FR-001, NFR-005, API-001–API-003; UI-001. Private reports require an actual server boundary before owner data is exposed.
- **Approach:** Add explicit pilot configuration and one configured owner hash; use the approved UI-plan auth proposal, opaque hashed-at-rest SQLite session tokens, CSRF, logout/revocation, generic bounded sign-in throttling and safe local return paths. Pilot mode denies all legacy anonymous content endpoints and source assets; missing auth configuration stays locked. Default public-site behavior is not silently deployed or replaced.
- **Library / dependency notes:** Plan pwdlib[argon2] for password hashing; verify official docs and pin/test its version when implementing. Use secrets and existing SQLite for sessions; no new paid identity service or JWT dependency.
- **Acceptance criteria:**
  - [ ] Unauthenticated, expired, revoked, tampered and CSRF-invalid requests cannot read or mutate pilot content.
  - [ ] Login, logout, credential rotation and operator recovery are documented and tested; no public registration exists.
  - [ ] Pilot mode blocks legacy anonymous API/page/export access; liveness discloses no private content.
  - [ ] Secure/HttpOnly/SameSite cookie and agreed lifetime are enforced; no secrets appear in HTML/logs.
- **Test plan:** New auth integration tests with temporary SQLite plus sign-in/logout/session-expiry browser flow in tests/e2e. Retain legacy tests outside pilot mode.
- **Out of scope:** Team accounts, hosted OAuth, email recovery, production cutover.
- **Bump:** minor
- **Status:** open
- **Depends on:** None
- **Execution gate:** Ready: owner authentication/session defaults approved. Verify and pin hashing dependency when implementing.
- **Docs:** docs/DATA_CONTRACTS.md API-001; docs/ARCHITECTURE.md §7.1; README.md private-mode configuration

### [FEAT-1792003577] Create private investigations with immutable source provenance

- [ ] **Priority:** high
- **Area:** api, storage
- **File(s):** backend/database.py, backend/models.py, backend/main.py; new backend/workbench_models.py, backend/workbench_repository.py, tests/integration/test_investigations.py
- **Why:** FR-002, FR-005, FR-012, API-004–API-007; ENT-002–ENT-004.
- **Approach:** Introduce a separate pilot database/repository namespace with owner-bound investigations, immutable source identity/version fields and fixed expiration metadata. Add create/list/detail contracts, optimistic versions and non-disclosing missing/expired-resource responses. Do not import old scraped video data automatically.
- **Library / dependency notes:** Reuse aiosqlite and Pydantic; use standard-library UUID/hash/time handling. No ORM/database migration dependency is required.
- **Acceptance criteria:**
  - [ ] Owner can create, list and retrieve only unexpired investigations with stable IDs and server-derived ownership.
  - [ ] Duplicate create requests are idempotent; stale writes conflict instead of overwriting.
  - [ ] Source identity, original/parsed text mapping and provenance support later parser/claim work without video-ID coupling.
  - [ ] Legacy database and seeded reports remain untouched; no public route exposes the pilot database.
- **Test plan:** Integration CRUD, ownership, idempotency, expiration and migration-isolation cases; unit schema validation.
- **Out of scope:** Parsing files, paid extraction, report generation, historical-data migration.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003576
- **Execution gate:** Ready: fixed creation-based retention approved.
- **Docs:** docs/DATA_CONTRACTS.md ENT-002–ENT-004; README.md database separation

### [FEAT-1792003578] Build the private workspace shell and investigations dashboard

- [ ] **Priority:** high
- **Area:** ui, api, tests
- **File(s):** frontend/styles.css, frontend/common.js, frontend/theme-init.js, backend/main.py; new frontend/workbench.html, frontend/workbench.js, tests/e2e/test_workbench_dashboard.py
- **Why:** FR-001–FR-002, NFR-004–NFR-005; UI-001–UI-002.
- **Approach:** Implement the shared shell, Investigations/Usage navigation, owner logout, local investigation tabs, theme tokens and real owner API-driven dashboard. Add empty, loading, failed, expired-session and setup-required states. Dashboard shows title, timestamps, expiry and actual job/report state rather than video scores.
- **Library / dependency notes:** Retain plain HTML/CSS/JavaScript and existing theme/escaping utilities. No frontend framework, CDN fonts or analytics.
- **Acceptance criteria:**
  - [ ] A signed-in owner can create/open an investigation from the dashboard; anonymous content stays inaccessible.
  - [ ] Dark/light states, visible keyboard focus and responsive layout follow the UI plan.
  - [ ] Empty/error/loading states do not substitute demo data or label liveness as research success.
  - [ ] No public Browse/channel ranking/share-link navigation appears in the pilot shell.
- **Test plan:** Seeded private browser dashboard/login/logout, theme and narrow-screen checks; API contract fixtures are explicitly labeled.
- **Out of scope:** Import parsing, evidence comparison, replacing the current production public site.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003576, FEAT-1792003577
- **Execution gate:** Ready: UI direction and browser/accessibility target approved.
- **Docs:** docs/UI_OVERHAUL.md UI-001–UI-002; screenshot documentation after real screens exist

### [FEAT-1792003579] Import and preview authorized TXT, SRT, VTT and pasted material

- [ ] **Priority:** high
- **Area:** api, ui, storage, security
- **File(s):** backend/main.py, backend/models.py; new backend/services/document_service.py, frontend/import.html, frontend/import.js, tests/unit/test_document_parser.py, tests/integration/test_document_import.py, tests/e2e/test_document_import.py
- **Why:** FR-003–FR-005, NFR-002, CON-004; UI-003; API-006–API-007.
- **Approach:** Add bounded local UTF-8 import with paste/file tabs, parser preview, original/normalized mapping and cue preservation. Enforce proposed 1 MiB transport bound before buffering, approved word limit, eligible format and required authorization/non-confidential declarations. Save source separately from paid extraction. Reference URL is metadata only.
- **Library / dependency notes:** Prefer tested small Python parsing functions for the supported subset; evaluate a parser package only if needed for correct SRT/VTT handling. No downloader/transcription dependency.
- **Acceptance criteria:**
  - [ ] All four accepted input modes preserve original text and inspectable source locations; missing times stay absent.
  - [ ] 10,001 words, byte overflow, invalid UTF-8, malformed/unsupported files and missing eligibility are rejected without provider calls.
  - [ ] Source label/basis and optional context are saved; imported markup cannot execute as HTML.
  - [ ] Validation preserves editable user input, reports cue/line errors where available and supports a normal file picker.
- **Test plan:** Parser normal/boundary/malformed/markup fixtures; streaming byte-bound integration test; browser paste/upload/preview/eligibility journey.
- **Out of scope:** Media, PDFs/DOCX, arbitrary URLs, silent full-page downloads, paid extraction.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003577, FEAT-1792003578
- **Execution gate:** Ready: 1 MiB/UTF-8 bound approved; prove resource behavior and bounded token/markup handling in parser tests (TBD-005 remainder).
- **Docs:** docs/DATA_CONTRACTS.md ENT-003/API-006; docs/UI_OVERHAUL.md UI-003; README.md supported inputs

### [FEAT-1792003580] Gate model and evidence integrations on recorded use policies

- [ ] **Priority:** high
- **Area:** api, services, security, storage
- **File(s):** backend/config.py, backend/services/llm.py, backend/services/search_service.py; new backend/services/provider_policy.py, tests/unit/test_provider_policy.py, tests/services/test_policy_gates.py
- **Why:** FR-008, FR-013, IR-002, NFR-007; ENT-007; UI-008.
- **Approach:** Add versioned provider-use configuration with explicit allowed operations/fields, attribution, retention/export conditions, dated prices and disclosure versions. Unverified/missing intended-use rights disable the relevant saved-report path. Filter before persistence and again on export; no unrestricted shared passage cache.
- **Library / dependency notes:** Use existing configuration/Pydantic/httpx mechanisms. No new provider/account signup or paid contract is part of this code ticket.
- **Acceptance criteria:**
  - [ ] Absent, disabled or expired policy prevents affected external calls and persistence/export.
  - [ ] Tests demonstrate allowed/forbidden excerpts, metadata, derived reports and export paths without treating privacy as a license.
  - [ ] Policy snapshots contain no credentials and preserve required source/publisher attribution.
  - [ ] A machine-readable capability state distinguishes policy/pricing readiness from process liveness.
- **Test plan:** Policy unit matrix and service integration tests with fake provider data; no live calls needed to prove fail-closed behavior.
- **Out of scope:** Purchasing rights, claiming legal clearance, selecting an unverified supplier, scraping around a disabled integration.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003577
- **Execution gate:** Implementation of fail-closed controls is ready; actual enablement remains blocked on TBD-001 verified provider entitlements.
- **Docs:** docs/EVIDENCE_PROVIDER_FEASIBILITY.md verified entitlement references; docs/DATA_CONTRACTS.md ENT-007; operator configuration

### [FEAT-1792003581] Enforce monthly research reservations and content-free usage accounting

- [ ] **Priority:** high
- **Area:** services, storage, api
- **File(s):** backend/config.py, backend/database.py, backend/services/llm.py; new backend/services/budget_service.py, tests/unit/test_budget.py, tests/integration/test_budget_admission.py
- **Why:** FR-017–FR-018, CON-002; ENT-009; API-015.
- **Approach:** Implement integer USD-microdollar ledger and configurable billing-period allowances; admit complete bounded operation plans transactionally. Separate incurred, reserved and uncertain costs, price versions and hosting assumptions. Failed/deleted work does not refund actual usage; unknown prices and retries/fallbacks require valid reserves.
- **Library / dependency notes:** Reuse SQLite transactions and standard-library integers/time. Model SDK retry/fallback behavior must be bounded/rated, not silently accepted.
- **Acceptance criteria:**
  - [ ] Simultaneous admissions cannot overspend the variable allowance; unknown prices or insufficient funds start no paid call.
  - [ ] Known charges and unresolved reservations survive job failure/deletion without source/query text.
  - [ ] Token/cache/search categories and retries settle once per operation ID, without double counting.
  - [ ] Budget response distinguishes proposed operating allocation, application usage and external invoices.
- **Test plan:** Exact-money/rounding tests; concurrent transaction admission; failure/unknown billing; deletion invariance; UTC-period boundary.
- **Out of scope:** Payments, billing users, guaranteeing an external account's total bill, changing the approved USD 25 operating constraint.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003577, FEAT-1792003580
- **Execution gate:** Confirm configured allocation and actual prices before live enablement (TBD-001/TBD-002); code invariants test offline.
- **Docs:** docs/DATA_CONTRACTS.md ENT-009/API-015; README.md budget configuration; docs/ARCHITECTURE.md accounting

### [FEAT-1792003582] Run durable extraction and research jobs with one fenced executor

- [ ] **Priority:** high
- **Area:** services, storage, api
- **File(s):** backend/services/pipeline.py, backend/main.py, backend/database.py; new backend/services/workbench_jobs.py, tests/services/test_workbench_jobs.py, tests/integration/test_job_recovery.py
- **Why:** FR-016–FR-018, NFR-001; ENT-008; API-008/API-010/API-011; UI-007.
- **Approach:** Create durable queued/running/terminal states with immutable document/claim snapshots, idempotency, complete admission plans and one deployment-wide executor lease. Fence stale workers, check parent/policy/budget before each paid call, and make interrupted ambiguous work require explicit resubmission.
- **Library / dependency notes:** Reuse asyncio/aiosqlite; no hosted queue. Disable or explicitly budget SDK automatic paid retries.
- **Acceptance criteria:**
  - [ ] Two simultaneous eligible jobs execute at most one paid job; polling never launches work.
  - [ ] Restart preserves status and marks abandoned paid work interrupted without duplicate billing calls.
  - [ ] Partial/failed/interrupted/cancelled states are distinct from successful insufficient evidence.
  - [ ] Lease loss, expiry and deletion prevent stale content writes while content-free settlement remains possible.
- **Test plan:** Concurrency, crash/restart, lease generation, duplicate request, timeout/uncertain billing and deleted-parent tests.
- **Out of scope:** Distributed scaling, automatic replay of ambiguous calls, UI-specific evidence editing.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003581
- **Execution gate:** None for offline/durable executor work; live adapters remain policy-gated.
- **Docs:** docs/DATA_CONTRACTS.md ENT-008; docs/ARCHITECTURE.md ADR-004; VERIFICATION.md recovery procedure

### [FEAT-1792003583] Extract locatable candidate claims from supplied documents

- [ ] **Priority:** high
- **Area:** services, api, ui
- **File(s):** backend/services/claim_extractor.py, backend/services/llm.py; new backend/services/document_claims.py, tests/services/test_document_claims.py, tests/e2e/test_claim_extraction.py
- **Why:** FR-005–FR-006, FR-016–FR-017; UI-003–UI-004; API-008–API-010.
- **Approach:** Adapt extraction to immutable document context, real source offsets and optional cue times; validate exact source quotes before retaining candidates. Run through admitted durable jobs and return empty-result/failure states truthfully. Show extraction progress without automatic evidence research.
- **Library / dependency notes:** Reuse the existing Anthropic structured-call adapter/schema validation after policy/budget integration; no new model choice.
- **Acceptance criteria:**
  - [ ] Candidates link to exact original passages and real available cue times; malformed/unlocatable candidates are rejected.
  - [ ] No-candidate content is explicit and distinct from refusal/provider failure.
  - [ ] Extraction is a separate user-initiated paid action with disclosure and usage accounting.
  - [ ] Supplied content instructions cannot change model policy, owner permissions, or budget configuration.
- **Test plan:** Structured response, source quote/location, prompt-injection fixture, empty/refusal/provider failure and browser progress cases.
- **Out of scope:** Whole-platform transcripts, image/media interpretation, evidence retrieval or scoring creator credibility.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003579, FEAT-1792003582
- **Execution gate:** Live extraction requires verified Anthropic intended-use/disclosure and valid pricing (TBD-001). Offline fixture implementation is ready.
- **Docs:** docs/DATA_CONTRACTS.md claim mapping; docs/UI_OVERHAUL.md UI-004; methodology documentation

### [FEAT-1792003584] Review, correct and freeze a bounded claim selection

- [ ] **Priority:** high
- **Area:** ui, api, storage
- **File(s):** frontend/claims.js, backend/models.py; new frontend/claim-review.js, tests/integration/test_claim_revisions.py, tests/e2e/test_claim_review.py
- **Why:** FR-005, FR-007, FR-012, NFR-002; UI-004; API-009/API-011.
- **Approach:** Implement side-by-side source/candidate review with editable standalone wording, immutable quotes, saved revision state and n/10 selection. Research confirmation shows disclosure/estimate and submits frozen revision IDs only after explicit action. Handle stale revisions without erasing local edits.
- **Library / dependency notes:** Reuse safe HTML rendering and existing component utilities; no rich text framework.
- **Acceptance criteria:**
  - [ ] Owner can correct wording/context while source quotes remain immutable and source passages are inspectable.
  - [ ] The server rejects zero/over-limit/cross-document selections and stale revisions.
  - [ ] Checkbox selection alone does not start paid work; confirmation names the actual saved selection.
  - [ ] Later edits do not mutate the running job snapshot.
- **Test plan:** Revision/selection API tests; keyboard selection, limit enforcement, conflict recovery and source highlighting browser cases.
- **Out of scope:** Evidence presentation, report editing, combining multiple source documents into one job.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003583
- **Execution gate:** Ready when listed prerequisites are complete.
- **Docs:** docs/UI_OVERHAUL.md UI-004; API-009/API-011 contract examples

### [FEAT-1792003585] Retrieve policy-permitted supporting and conflicting evidence

- [ ] **Priority:** high
- **Area:** services, storage, api
- **File(s):** backend/services/search_service.py, backend/services/source_quality.py; new tests/services/test_workbench_evidence.py
- **Why:** FR-008, FR-010, IR-002; ENT-005; provider feasibility findings.
- **Approach:** Adapt Brave/Google retrieval to frozen selected claims under the policy/budget executor; distinguish errors from no results. Preserve coverage, dates, publisher verdicts, passage identity, source rights and retention bounds. Query both support and contradiction; persist only permitted evidence, with no assumed 14-day cache rights.
- **Library / dependency notes:** Reuse existing httpx/provider clients; new supplier requires separate verified terms/configuration. A source URL is not a grant to fetch full pages.
- **Acceptance criteria:**
  - [ ] All retained evidence has source identity, retrieval provenance, coverage and applicable policy/expiry.
  - [ ] Professional ratings are separate from product assessments and match the actual proposition/time/scope under review.
  - [ ] Provider failure/disabled permission is explicit and cannot become a confident no-evidence conclusion.
  - [ ] No disallowed returned content enters caches, diagnostics or exports.
- **Test plan:** Mocked provider payloads including cache headers/forbidden fields; matching context and date tests; separately authorized real-provider trial.
- **Out of scope:** Scraping publishers, purchasing licenses, unapproved transcript providers, automatic whole-page fetching.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003584, FEAT-1792003580, FEAT-1792003581
- **Execution gate:** Live retrieval and persisted/exported provider material are BLOCKED until TBD-001 intended-use rights and pricing are established.
- **Docs:** docs/EVIDENCE_PROVIDER_FEASIBILITY.md entitlement record; docs/DATA_CONTRACTS.md ENT-005/§7

### [FEAT-1792003586] Generate evidence-linked draft assessments with validated citations

- [ ] **Priority:** high
- **Area:** services, api, storage
- **File(s):** backend/services/fact_checker.py, backend/models.py; new tests/services/test_workbench_assessments.py, tests/unit/test_document_citations.py
- **Why:** FR-009–FR-010, FR-012, NFR-004; ENT-006.
- **Approach:** Generate supported/contradicted/mixed/insufficient-evidence/non-factual draft states from the research snapshot. Reject unknown evidence IDs and nonmatching quotes, retain context/coverage limitations, and label AI authorship. Preserve partial failures and researcher review as separate concepts; do not map labels to a creator truth percentage.
- **Library / dependency notes:** Reuse structured model output and existing grounding functions after adapting source identity/coverage. No new model selection.
- **Acceptance criteria:**
  - [ ] Fabricated source IDs/quotes cannot become validated citations; matching text does not imply contextual review.
  - [ ] Drafts retain evidence stance, limitations and provider failure coverage.
  - [ ] Report provenance records document/claim/model/prompt/policy references for the exact job.
  - [ ] No overall video/channel credibility score is produced.
- **Test plan:** Citation identity/negation/ellipsis/context cases; no-evidence/refusal/partial-failure response tests and immutable snapshot checks.
- **Out of scope:** Automated editorial certification, public publication, domain-based reliability as a substitute for evidence review.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003585
- **Execution gate:** Live inference requires the applicable approved policy; quality thresholds/corpus remain evaluation decisions TBD-003/TBD-004.
- **Docs:** docs/UI_OVERHAUL.md UI-005–UI-006; methodology limitations; report contract

### [FEAT-1792003587] Build the source and evidence comparison workbench

- [ ] **Priority:** high
- **Area:** ui, tests
- **File(s):** frontend/styles.css, frontend/claims.js, frontend/common.js; new frontend/evidence-workbench.js, tests/e2e/test_evidence_workbench.py
- **Why:** FR-005, FR-008–FR-010, FR-012; UI-005 and UI-007.
- **Approach:** Implement the compact claim list, readable source/context pane and evidence pane using real API records. Synchronize claim/source/evidence selection; show support/contradiction/context, coverage/date and quote-match/context-review labels. Adapt three panels into keyboard-operable smaller-screen tabs.
- **Library / dependency notes:** Plain CSS grid and small JavaScript modules; retain theme utilities. No player, screen scraper or external component framework.
- **Acceptance criteria:**
  - [ ] Selecting a claim reveals the matching source passage and actual retrieved evidence without conflating publisher and model verdicts.
  - [ ] Unknown dates, partial jobs and expired/restricted evidence remain explicit.
  - [ ] Keyboard navigation and pane switching preserve context; color is not the only assessment cue.
  - [ ] Loading/error/no-results fixtures are visibly distinct; no hidden automatic source downloads occur.
- **Test plan:** Browser tests for source alignment, supporting/conflicting evidence, coverage, unavailable evidence, keyboard focus and responsive panes.
- **Out of scope:** Report version editing/export, whole-document third-party content replication, in-app public links.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003586, FEAT-1792003578
- **Execution gate:** Can build/render with clearly labeled offline fixtures; live verification still depends on evidence rights.
- **Docs:** docs/UI_OVERHAUL.md UI-005/UI-007; actual workbench screenshots after implementation

### [FEAT-1792003588] Edit report revisions and explicitly record researcher review

- [ ] **Priority:** high
- **Area:** ui, api, storage
- **File(s):** backend/main.py, backend/models.py; new frontend/report-editor.js, tests/integration/test_report_revisions.py, tests/e2e/test_report_review.py
- **Why:** FR-011–FR-012, NFR-004; UI-006; API-012.
- **Approach:** Add immutable report revisions with optimistic concurrency, explicit draft/reviewed labels, researcher notes and confirmation. Editing a reviewed revision creates a draft unless the resulting revision is explicitly reviewed; revalidate modified citation references and distinguish owner conclusions.
- **Library / dependency notes:** Use plain textarea/forms for pilot editing; no WYSIWYG/Markdown-rendering dependency unless separately justified and safely sanitized.
- **Acceptance criteria:**
  - [ ] Owner can edit notes/conclusions and review a chosen revision with an audit trail.
  - [ ] Changes never silently inherit reviewed status or overwrite historical inputs/evidence.
  - [ ] Conflicts preserve local input and require a deliberate resolution.
  - [ ] Uncited owner judgment cannot masquerade as a validated AI citation.
- **Test plan:** Version lineage, review transitions, concurrent revision and citation tamper integration tests; browser save/review/conflict journey.
- **Out of scope:** Collaborative editing, public publishing, automatic send/email.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003587
- **Execution gate:** Ready when listed prerequisites are complete.
- **Docs:** docs/DATA_CONTRACTS.md ENT-006/API-012; docs/UI_OVERHAUL.md UI-006

### [FEAT-1792003589] Download policy-filtered Markdown and JSON report exports

- [ ] **Priority:** high
- **Area:** api, ui, security
- **File(s):** backend/main.py, backend/models.py; new backend/services/report_export.py, tests/unit/test_report_export.py, tests/integration/test_private_exports.py, tests/e2e/test_report_export.py
- **Why:** FR-013, IR-002, NFR-004, CON-003; UI-006; API-013.
- **Approach:** Serialize selected immutable revisions to equivalent Markdown/ExportEnvelope outputs, rechecking current permitted fields/retention. Include review state, source/citation provenance and explicit omissions. Stream authenticated no-store attachments; exclude whole transcripts, secrets and raw provider result dumps.
- **Library / dependency notes:** Standard-library JSON and explicit Markdown serialization; no PDF/DOCX conversion service.
- **Acceptance criteria:**
  - [ ] Markdown and JSON identify the same report revision/findings/review state and preserve attribution.
  - [ ] Restricted/expired fields are omitted with limitations or the export is refused if not useful/permitted.
  - [ ] Unauthorized or deleted/expired exports fail; no public share URL or server export archive is created.
  - [ ] Browser download is user-initiated and explains that external copies cannot be recalled.
- **Test plan:** Golden meaningful field/permission/revision tests; authenticated attachment headers; private browser download checks.
- **Out of scope:** Public URLs, email delivery, PDF/Word export, full-source archival bundles.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003588, FEAT-1792003580
- **Execution gate:** Actual retained/exported evidence use requires TBD-001 rights; fixture/manual-content export logic can proceed.
- **Docs:** docs/DATA_CONTRACTS.md ExportEnvelope; docs/UI_OVERHAUL.md UI-006; README.md export scope

### [FEAT-1792003590] Delete investigations immediately while fencing active paid work

- [ ] **Priority:** high
- **Area:** api, storage, services, ui, security
- **File(s):** backend/database.py, backend/main.py; new tests/integration/test_investigation_deletion.py, tests/services/test_deleted_job_fencing.py, tests/e2e/test_investigation_delete.py
- **Why:** FR-014, FR-018, NFR-005; UI-008; API-014.
- **Approach:** Coordinate confirmed owner deletion, admission closure/executor fencing, content cascade and temporary-buffer cleanup. Late provider responses may settle detached content-free usage only. Use the approved dedicated-store/purge proposal and document its exact SQLite/host limitations.
- **Library / dependency notes:** Reuse SQLite transactions and task cancellation; validate secure-delete/journal behavior rather than assuming row deletion erases all physical copies.
- **Acceptance criteria:**
  - [ ] After success all active investigation/source/claim/evidence/report/job reads/exports are unavailable.
  - [ ] No new paid call starts after successful deletion; late responses cannot resurrect content.
  - [ ] Incurred and uncertain accounting remains without query/passage/source content or case links.
  - [ ] UI names the case and accurately distinguishes application deletion, provider/host limits and downloaded copies.
- **Test plan:** Deletion during queue/provider await/report write/export; retry/idempotency; storage content inspection appropriate to chosen SQLite mode; browser confirmation.
- **Out of scope:** Recalling downloaded files, promising instantaneous provider/host-disk erasure, inventing a backup retention contract.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003589, FEAT-1792003582, FEAT-1792003581
- **Execution gate:** No-automatic-backup policy approved; verify physical cleanup and disclose actual host/provider-copy limitations before enabling live deletion promises (TBD-006 remainder).
- **Docs:** docs/ARCHITECTURE.md ADR-007; docs/DATA_CONTRACTS.md §8; deletion disclosure/runbook

### [FEAT-1792003591] Expire investigations and enforce cleanup across restart and reads

- [ ] **Priority:** high
- **Area:** storage, services, api
- **File(s):** backend/database.py, backend/main.py; new backend/services/retention_service.py, tests/integration/test_investigation_expiry.py
- **Why:** FR-015, FR-016, NFR-005; ENT-002; UI-008.
- **Approach:** Use the fixed creation-time retention deadline, access-time checks, startup-before-access purge and periodic/pre-execution cleanup. Apply the deletion/fencing path and earlier evidence-use deadlines; editing never extends retention. Disable unapproved automatic content backups and define a tested restore policy before enabling them.
- **Library / dependency notes:** Reuse asyncio scheduling and timezone-aware standard-library time; no hosted scheduler.
- **Acceptance criteria:**
  - [ ] Expired content is inaccessible even before physical maintenance runs or after offline restart.
  - [ ] Queued/running work and dependent citations cannot bypass parent or evidence expiration.
  - [ ] Edit/access never resets the fixed deadline; UI shows accurate expiry.
  - [ ] Ledger reconciliation survives expiry; restoring permitted state cannot re-expose deleted/expired content.
- **Test plan:** Fake-clock boundary, offline/startup, mid-job evidence expiry and restore-reconciliation tests; no data-wiping test against owner storage.
- **Out of scope:** Sliding retention, indefinite extension, unapproved backup automation.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003590
- **Execution gate:** Fixed clock and no-automatic-backup policy approved. Verify actual physical cleanup/restore limitations (TBD-006 remainder).
- **Docs:** VERIFICATION.md retention/recovery checks; docs/DATA_CONTRACTS.md §8

### [FEAT-1792003592] Show truthful progress, research availability and operating usage

- [ ] **Priority:** high
- **Area:** ui, api, tests
- **File(s):** frontend/common.js, backend/main.py; new frontend/usage.html, frontend/usage.js, frontend/job-status.js, tests/e2e/test_workbench_usage.py
- **Why:** FR-016–FR-018, NFR-006–NFR-007, CON-002; UI-007–UI-008; API-010/API-015.
- **Approach:** Add owner-facing usage and provider-processing notices plus reusable real job status. Show known/reserved/uncertain amounts, configuration readiness and remaining allowance without pretending they are the final external bill. Resubmission repeats disclosure/admission and never silently replays failed paid work.
- **Library / dependency notes:** Reuse native browser APIs/CSS; no analytics/monitoring SaaS.
- **Acceptance criteria:**
  - [ ] Budget exhausted, rights disabled, pricing unknown, queued, partial, interrupted and cancelled states have distinct useful explanations.
  - [ ] Status polling never starts work or leaks content after logout/deletion/expiry.
  - [ ] Read/review/export stays usable when only research funds are exhausted; host shutdown is not represented as supported online operation.
  - [ ] Logs and UI contain no raw provider exception/request/credential text.
- **Test plan:** API fixture states plus browser cancellation/session-expiry/budget boundaries; content-free diagnostic assertions.
- **Out of scope:** Owner billing, supplier admin dashboards, external account invoice synchronization.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003582, FEAT-1792003581, FEAT-1792003578, FEAT-1792003590
- **Execution gate:** Display actual verified policy notices before live use; account cost reconciliation remains TBD-002.
- **Docs:** docs/UI_OVERHAUL.md UI-007–UI-008; README.md truthful availability/usage

### [FEAT-1792003593] Complete keyboard, responsive and research-quality pilot acceptance

- [ ] **Priority:** med
- **Area:** ui, tests, docs
- **File(s):** tests/e2e/conftest.py, tests/e2e/test_frontend.py, scripts/screenshots.py, frontend/styles.css; new tests/e2e/test_workbench_accessibility.py, docs/PILOT_EVALUATION.md
- **Why:** NFR-003–NFR-005, NFR-008, SRS §4/TBD-003/TBD-004/resolved TBD-007; UI_OVERHAUL.md §5–§7.
- **Approach:** Complete keyboard/focus/announcement/reflow and theme checks for the real private workflow, preserve old tests separately and capture new screenshots. Use explicit fixture material to verify claim/citation/context failure cases; record permitted live-provider trials, measured time/cost and researcher judgments without inventing accuracy/SLA thresholds.
- **Library / dependency notes:** Reuse pytest-playwright; evaluate/pin an automated accessibility helper only if justified. Automated checks supplement manual keyboard/assistive-tech review.
- **Acceptance criteria:**
  - [ ] Approved core-flow WCAG 2.2 AA target is evaluated with automated and manual evidence, without an unearned certification statement.
  - [ ] Core import/select/evidence/review/export/delete flows work at proposed breakpoints and both themes.
  - [ ] Every Must requirement has a proving test or explicit inspection/demo evidence; seeded tests are not reported as live-provider proof.
  - [ ] Evaluation records outstanding corpus/quality/performance/volume decisions and clearly separates implementation-ready from launch-ready.
- **Test plan:** Private E2E matrix; manual keyboard/focus/reflow/contrast checks; representative research evaluation and cost trial only with authorized provider rights.
- **Out of scope:** Claiming statistical accuracy from a tiny corpus, production release/deploy, paid third-party audits.
- **Bump:** minor
- **Status:** open
- **Depends on:** FEAT-1792003591, FEAT-1792003592, FEAT-1792003589
- **Execution gate:** Final measured thresholds/corpus and operator release decisions remain TBD-002–TBD-004; independent UI quality work can start after prerequisites.
- **Docs:** docs/PILOT_EVALUATION.md; VERIFICATION.md baseline/proving coverage; README.md actual supported browser matrix


---

## Shipped

_No features shipped._
