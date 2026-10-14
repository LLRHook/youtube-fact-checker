# Software Requirements Specification — Research Evidence Workbench

Uses the SRS content outline of ISO/IEC/IEEE 29148:2018 §9.6; this is not a certification claim.
Related: [Data Contracts](DATA_CONTRACTS.md) · [Architecture](ARCHITECTURE.md)
Status: Draft — stakeholder pilot scope approved; open engineering and provider decisions remain.

## 1. Introduction

### 1.1 Purpose

Specify a private pilot that helps a researcher identify claims in supplied material, inspect evidence, and produce a reviewed research report. This document owns required behavior and acceptance criteria. The linked documents own data shapes and the proposed implementation. “Research Evidence Workbench” is a descriptive working name.

The requirements interview authorized documentation. The subsequent planning request authorizes a UI overhaul plan, grooming, and committing/pushing the planning work. Backlog filing follows its explicit review gate. Implementation, purchases, account changes, merges, and deployment remain separate. Requirements describe the intended product, not the current application's conformance.

### 1.2 Scope

The initial user is the owner acting as a researcher or journalist. Inputs are authorized public or non-confidential text, scripts, and transcript files. Reports are private; sharing in this pilot means explicitly downloading an export and distributing it outside the application. The system proposes assessments; the researcher owns editorial conclusions.

The pilot does not automatically obtain material from arbitrary YouTube URLs, transcribe uploaded media, host public reports, offer team collaboration, or score creator credibility. Optional source URLs are references, not instructions to fetch their content.

Success is demonstrated by the workflow in §4 and inspection of retained citations and source locations. Accuracy, time-saved, latency, and report-volume thresholds are unresolved in TBD-003 and TBD-004. No accuracy percentage or monthly report count is promised.

### 1.3 Product perspective

This is a proposed evolution of the existing Python/FastAPI web application, retaining useful extraction, research, report, and usage-accounting components. Existing anonymous video APIs, video-centric persistence, and scraping are not the new private workflow. See [Architecture §3](ARCHITECTURE.md#3-system-context-c4-level-1).

#### 1.3.1 System interfaces

Owner-facing REST operations are API-001–API-015. Provider interaction is described in Data Contracts §7; it is server-side and conditional on approved use rights.

#### 1.3.2 User interfaces

Browser surfaces: sign-in, investigation list, document import/preview, candidate-claim selection, job progress, evidence/assessment review, report editor/export, and deletion. Desktop browser first; supported browsers and accessibility target are TBD-007. Private content is absent from anonymous navigation and public indexing.

The requested screen-by-screen overhaul, interaction states, design system, proposed browser/accessibility defaults, and migration map are in [UI_OVERHAUL.md](UI_OVERHAUL.md). The complete proposed implementation backlog and its decision gates are in [GROOMING.md](GROOMING.md); its proposed defaults do not silently resolve the TBDs below.

#### 1.3.3 Hardware interfaces

No specialized hardware interfaces: the pilot is a browser and web service.

#### 1.3.4 Software interfaces

Retain Python 3.13, FastAPI, plain HTML/JavaScript/CSS, SQLite, and Docker under CON-001. Existing Anthropic and evidence-provider adapters are candidates for reuse, not proof of permission or runtime availability. External integration details are Data Contracts §7 and IR-002.

#### 1.3.5 Communications interfaces

Browser and external provider traffic use HTTPS outside local development. A session authenticates owner API requests. Job status is polled through API-010; no streaming protocol or external message broker is required by this scope.

#### 1.3.6 Memory constraints

The text/claim limits are NFR-002. Byte-size, resource sizing, and handling of unusually large single tokens are TBD-005; no unbounded upload allocation is acceptable. There is no approved numeric RAM budget.

#### 1.3.7 Operations

One owner and one executing paid job at a time. Normal operations are import, extraction, selected-claim research, review, export, expiration, and deletion. At an exhausted research allowance, existing authorized data remains available for review/export while new paid work is refused. Backup retention, recovery targets, and external-provider deletion exceptions are TBD-006. Owner-operated pilot; no support-hours or uptime SLA is agreed.

#### 1.3.8 Site adaptation requirements

Deployment needs owner authentication configuration, provider credentials, allowed-use policies, dated price configuration, spending limits, and persistent storage. Existing Railway hosting is a candidate under CON-001; its actual entitlement and consumption are unverified.

### 1.4 Product functions

- Private access and investigation organization: FR-001–FR-002.
- Supplied-material ingestion, eligibility, and provenance: FR-003–FR-005.
- Claim extraction, researcher selection, and evidence research: FR-006–FR-008.
- Citation validation and draft assessments: FR-009–FR-010.
- Human review, revision history, and export: FR-011–FR-013.
- User deletion and automatic expiration: FR-014–FR-015.
- Job progress, budget admission, and usage accounting: FR-016–FR-018.

### 1.5 User characteristics

| User class | Description | Technical expertise | Permissions |
|---|---|---|---|
| Owner/researcher | Sole pilot account; investigates supplied material | Can evaluate sources; no programming required for ordinary use | Own investigations, research, review, export, delete |
| Unauthenticated visitor | No pilot data access | Any | Sign-in and non-sensitive service availability only |
| Operator | Owner configuring the service | Deployment/configuration expertise | Configuration and recovery; no additional product user role |

### 1.6 Limitations

Supplied content still requires an appropriate acquisition and processing basis. This specification is not legal clearance. Caption errors, missing context, dated evidence, selective claim sampling, search coverage, and model errors can affect drafts. A quote that matches a search passage is not independently proof of contextual support. The pilot does not accept confidential source material; provider handling must still be disclosed.

### 1.7 Assumptions and dependencies

| Item | Consequence if false |
|---|---|
| The answer “25” means USD 25 total monthly operating spend | Revise CON-002 before enabling paid processing |
| One owner suffices for the pilot | Introduce multi-user isolation and role requirements before expanding access |
| Approved provider terms cover the exact intended processing/storage/export use | Disable the affected provider/path; resolve TBD-001 rather than bypass restrictions |
| Existing stack can operate within the allowance | Measure costs and revisit deployment; do not promise a hosted pilot within budget beforehand |
| Stakeholder-selected inputs are non-confidential and authorized | Reject disallowed submissions under FR-004; an attestation is not independent proof of rights |

### 1.8 Apportioning of requirements

| Phase | Scope | Exit criteria |
|---|---|---|
| Pilot | Must requirements below; one owner, supplied text/transcripts, reviewed private exports | §4 passes; provider-use and operational release dependencies resolved; budget measured |
| Production | Scope not approved | New requirements interview for support, volume, reliability, and users |
| Later | Media transcription, creator OAuth, team workspaces, in-app sharing links | Separate permission, cost, privacy, and requirements review |

## 2. References

Source keys used below:

| Key | Source |
|---|---|
| SRC-001 | Stakeholder interview, 2026-10-14: researcher/journalist audience; flexible ingestion workflow |
| SRC-002 | Stakeholder interview: text/scripts/TXT/SRT/VTT; private reports; answer “25” interpreted as USD/month |
| SRC-003 | Stakeholder interview: one authenticated owner; authorized non-confidential inputs; 30 days; immediate user deletion; Markdown/JSON |
| SRC-004 | Stakeholder pre-write approval: retain stack; 10,000 words/document; 10 selected claims/job; one concurrent research job; export-based sharing; explicit TBDs |
| SRC-005 | Approved pre-write functional summary: claim correction/selection, permitted evidence retrieval, draft assessments, human review, export, spending controls |
| SRC-006 | Derived engineering proposal necessary to satisfy approved privacy, provenance, deletion, or spending behavior; details remain subject to implementation review |

Supporting research: [Product feasibility](PRODUCT_FEASIBILITY.md), [Evidence-provider feasibility](EVIDENCE_PROVIDER_FEASIBILITY.md), checked 2026-10-14. These record primary platform/provider sources and unresolved account-specific rights. Applicable standards: ISO/IEC/IEEE 29148:2018 outline; no blanket standards conformance is asserted.

## 3. Requirements

### 3.1 Functions

#### FR-001 — Owner sign-in

The system shall authenticate the configured owner before granting investigation access.

- Priority: Must
- Rationale: Private access for the sole pilot user.
- Source: SRC-003
- Verification: Test
- Status: Approved
- Acceptance: Given an unauthenticated or expired session, when investigation data or exports are requested, then access is refused without disclosing content.
- Traces: ENT-001, API-001, API-002, API-003, CMP-001, CMP-002

#### FR-002 — Investigation organization

The system shall let the owner create and retrieve private investigations.

- Priority: Must
- Rationale: Organize each research task independently of a video ID.
- Source: SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given an authenticated owner, when an investigation is created and subsequently listed, then its title and identifier are available only to that owner.
- Traces: ENT-002, API-004, API-005, CMP-001, CMP-002, CMP-006

#### FR-003 — Text and transcript import

The system shall ingest pasted text or UTF-8 TXT, SRT, and VTT files into source documents.

- Priority: Must
- Rationale: Authorized supplied material replaces automatic platform extraction.
- Source: SRC-002
- Verification: Test
- Status: Approved
- Acceptance: Given each supported input, when imported, then the original material and a readable parsed representation are available; transcript cue times are preserved where present and absent times are not invented.
- Traces: ENT-003, API-006, API-007, CMP-001, CMP-002, CMP-003, CMP-006

#### FR-004 — Submission eligibility

The system shall reject submissions that do not declare an authorized non-confidential processing basis.

- Priority: Must
- Rationale: Enforce the pilot's agreed material scope.
- Source: SRC-003
- Verification: Test
- Status: Approved
- Acceptance: Given missing eligibility declarations or a confidential classification, when import is requested, then no source document is accepted and no provider is called.
- Traces: ENT-003, API-006, CMP-001, CMP-002, CMP-003

#### FR-005 — Source provenance

The system shall retain provenance linking each extracted claim to its immutable source document and original passage.

- Priority: Must
- Rationale: Researchers need to inspect what was actually said.
- Source: SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given a claim, when its source reference is opened, then the quoted passage matches the indicated source text and location; unknown speaker/date information is labeled unknown.
- Traces: ENT-003, ENT-004, API-007, API-009, CMP-003, CMP-006

#### FR-006 — Candidate claim extraction

The system shall propose factual claims from a researcher-selected source document.

- Priority: Must
- Rationale: Reduce manual identification work while preserving review.
- Source: SRC-005
- Verification: Demonstration, Test
- Status: Approved
- Acceptance: Given accepted source material, when extraction completes, then candidate claims show their proposed wording and source passages; a document with no candidates produces an explicit empty result.
- Traces: ENT-004, ENT-008, API-008, API-009, API-010, CMP-003, CMP-004

#### FR-007 — Claim correction and selection

The system shall let the researcher edit candidate wording and select claims before evidence research.

- Priority: Must
- Rationale: Human scope/context control and bounded spending.
- Source: SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given candidate claims, when the researcher edits and selects them, then research uses that saved revision and selection; the source quote remains unchanged.
- Traces: ENT-004, ENT-008, API-009, API-011, CMP-001, CMP-002, CMP-004

#### FR-008 — Permitted evidence research

The system shall retrieve evidence for selected claims only through enabled integrations whose intended use is authorized.

- Priority: Must
- Rationale: Product value must not depend on bypassing source restrictions.
- Source: SRC-001, SRC-005
- Verification: Test, Inspection
- Status: Approved
- Acceptance: Given an integration without the required processing/retention/export entitlement, when research is attempted, then that integration is not called; an approved integration records source and retrieval provenance.
- Traces: ENT-005, ENT-007, API-011, CMP-004, CMP-005

#### FR-009 — Citation integrity

The system shall exclude model-generated quotations that do not match identified retrieved evidence from cited report evidence.

- Priority: Must
- Rationale: Prevent invented quotations from appearing as supported evidence.
- Source: SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given an unknown evidence identifier or a quotation absent from that evidence, when an assessment is validated, then the quotation is rejected and cannot appear as a validated citation.
- Traces: ENT-005, ENT-006, API-012, CMP-004, CMP-005

#### FR-010 — Draft claim assessments

The system shall present claim assessments as AI-generated drafts with their cited evidence and limitations.

- Priority: Must
- Rationale: Evidence assistance rather than automatic editorial authority.
- Source: SRC-005
- Verification: Demonstration, Test
- Status: Approved
- Acceptance: Given completed research, when a draft is viewed, then supporting and conflicting evidence are distinguishable; a provider failure is distinguishable from insufficient evidence; no factual conclusion is labeled supported solely because a model asserted it.
- Traces: ENT-005, ENT-006, API-012, CMP-001, CMP-004

#### FR-011 — Researcher report review

The system shall let the researcher edit and explicitly mark a report revision as reviewed.

- Priority: Must
- Rationale: Retain human editorial responsibility.
- Source: SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given a draft report, when the owner changes a conclusion and confirms review, then the resulting revision records owner review; any subsequent change creates an unreviewed revision.
- Traces: ENT-006, API-012, CMP-001, CMP-002, CMP-006

#### FR-012 — Report revision provenance

The system shall retain the input, claim revision, model, and evidence references used for each retained report revision.

- Priority: Must
- Rationale: Distinguish researcher changes from generated drafts.
- Source: SRC-005; details SRC-006
- Verification: Test
- Status: Approved
- Acceptance: Given edited claims or a regenerated report, when earlier and later retained revisions are inspected, then each points to its own research snapshot and review state; source expiration removes dependent content under FR-015.
- Traces: ENT-004, ENT-005, ENT-006, ENT-008, API-012, CMP-004, CMP-006

#### FR-013 — Explicit report export

The system shall export an owner-selected report revision as Markdown or structured JSON only on an authenticated explicit request.

- Priority: Must
- Rationale: Private-by-default sharing through user-controlled downloads.
- Source: SRC-003, SRC-004
- Verification: Test
- Status: Approved
- Acceptance: Given either format, when export is requested, then the file identifies its revision and review state and contains only export-permitted fields; a draft is labeled unreviewed, and no public report URL is created.
- Traces: ENT-006, ENT-007, API-013, CMP-001, CMP-002, CMP-005

#### FR-014 — Immediate user deletion

The system shall remove an investigation and its content-bearing descendants from active application storage when the owner deletes it.

- Priority: Must
- Rationale: User control over retained investigations.
- Source: SRC-003
- Verification: Test
- Status: Approved
- Acceptance: Given queued or active jobs and an investigation, when deletion returns success, then reads/exports fail, future provider calls are prevented, and late responses cannot recreate its content; external-provider and backup limitations are separately disclosed.
- Traces: ENT-002, ENT-003, ENT-004, ENT-005, ENT-006, ENT-008, API-014, CMP-002, CMP-004, CMP-006

#### FR-015 — Investigation expiration

The system shall expire an investigation 30 days after its creation without resetting that deadline on access or editing.

- Priority: Must
- Rationale: Agreed retention default.
- Source: SRC-003; fixed creation-based interpretation SRC-006
- Verification: Test
- Status: Approved scope; retention-clock interpretation Proposed
- Acceptance: Given the expiration instant, when a read or job execution is attempted, then access/execution is refused; the expiration path applies the same active-storage deletion as FR-014.
- Traces: ENT-002, API-005, API-014, CMP-002, CMP-004, CMP-006

#### FR-016 — Durable job status

The system shall expose durable status for each accepted extraction or research job.

- Priority: Must
- Rationale: An online page must not hide a failed core workflow.
- Source: SRC-005; details SRC-006
- Verification: Test
- Status: Approved
- Acceptance: Given success, partial results, provider failure, interruption, or cancellation, when status is requested, then the persisted state reports that outcome and never presents incomplete research as completed.
- Traces: ENT-008, API-008, API-010, API-011, CMP-001, CMP-002, CMP-004, CMP-006

#### FR-017 — Paid-work budget admission

The system shall refuse a paid provider operation whose reserved maximum cost cannot fit the configured remaining allowance.

- Priority: Must
- Rationale: Bounded research spending within CON-002.
- Source: SRC-002, SRC-005
- Verification: Test
- Status: Approved
- Acceptance: Given exhausted funds, unknown applicable pricing, or insufficient reservation capacity, when work is requested or retried, then no affected paid call starts and a specific budget/pricing error is reported.
- Traces: ENT-007, ENT-008, ENT-009, API-008, API-011, API-015, CMP-004, CMP-005, CMP-006

#### FR-018 — Usage accounting

The system shall record paid-operation reservations and known incurred usage independently of retained investigation content.

- Priority: Must
- Rationale: Deleting or failing a job must not refund actual billed usage.
- Source: SRC-005; details SRC-006
- Verification: Test
- Status: Approved
- Acceptance: Given paid usage followed by job failure or investigation deletion, when remaining allowance is calculated, then incurred charges and unresolved reservations still reduce available funds without retaining source text.
- Traces: ENT-009, API-015, CMP-004, CMP-006

### 3.2 Performance requirements

#### NFR-001 — Executing-job concurrency

The system shall execute at most one paid extraction or research job at a time across the pilot deployment.

- Priority: Must
- Source: SRC-004
- Verification: Test
- Status: Approved
- Measure: Executing paid jobs <= 1 during simultaneous submissions and restart recovery.
- Acceptance: Given two eligible jobs, when both are admitted, then at most one begins external operations and the other remains queued.
- Traces: ENT-008, API-008, API-011, CMP-004, CMP-006

#### NFR-002 — Input and selection capacity

The system shall enforce limits of 10,000 whitespace-delimited words per document and 10 selected claims per research job.

- Priority: Must
- Source: SRC-004
- Verification: Test
- Status: Approved
- Measure: Accepted document words <= 10,000; researched selected claims <= 10.
- Acceptance: Given 10,001 words or 11 selected claims, when the corresponding request is submitted, then it is rejected before paid processing; permitted boundary cases are accepted.
- Traces: ENT-003, ENT-008, API-006, API-011, CMP-003, CMP-004

#### NFR-003 — Measured processing performance

The system should record extraction and research completion durations for representative pilot jobs.

- Priority: Should
- Source: SRC-004 (thresholds explicitly deferred)
- Verification: Analysis
- Status: Proposed — TBD-003
- Measure: Durations reported with input size, selected claim count, and provider outcome; latency percentile targets remain TBD.
- Acceptance: Given a representative completed or failed job, when evaluated, then duration and workload size are available without logging document text.
- Traces: ENT-008, ENT-009, API-010, CMP-004

### 3.3 Usability requirements

#### NFR-004 — Inspectable research state

The system shall distinguish model draft state from researcher-reviewed state in the report interface and exports.

- Priority: Must
- Source: SRC-005
- Verification: Demonstration, Test
- Status: Approved
- Measure: Every displayed/exported report revision includes a review-state label.
- Acceptance: Given a draft and a reviewed revision, when each is displayed/exported, then their labels distinguish them and do not imply platform or professional certification.
- Traces: ENT-006, API-012, API-013, CMP-001

Accessibility/browser targets remain TBD-007. Keyboard and assistive-technology checks are proposed verification work, not an invented stakeholder-approved certification target.

### 3.4 Interface requirements

#### IR-001 — Versioned browser API

The system shall expose the owner operations through the versioned contracts in Data Contracts §4.

- Priority: Must
- Source: SRC-006
- Verification: Test
- Status: Proposed design
- Acceptance: Given invalid input or a resource error, when an API operation responds, then the response uses the defined error envelope without source content or secrets.
- Traces: API-001, API-005, API-010, API-013, CMP-002

#### IR-002 — Provider policy enforcement

The system shall apply the enabled provider's recorded use policy to processing, retained evidence, and export.

- Priority: Must
- Source: SRC-005
- Verification: Test, Inspection
- Status: Approved scope; entitlement values TBD-001
- Acceptance: Given a policy forbidding retained excerpts or export, when that path is requested, then disallowed fields are not retained or exported; absent permission for a useful complete workflow prevents that provider from being enabled.
- Traces: ENT-007, API-011, API-013, CMP-004, CMP-005

### 3.5 Logical database requirements

Entity definitions and invariants are owned by Data Contracts §3:

| Entity | Meaning |
|---|---|
| ENT-001 | Owner principal/session association |
| ENT-002 | Investigation and retention deadline |
| ENT-003 | Immutable supplied source document |
| ENT-004 | Claim and claim revisions |
| ENT-005 | Permitted evidence item |
| ENT-006 | Report revision and review state |
| ENT-007 | Provider use/price policy |
| ENT-008 | Durable paid job and research snapshot |
| ENT-009 | Content-free usage/reservation ledger |

FR-014 and FR-015 own investigation deletion. Ledger, account/session, policy, backup, and provider-retention periods are distinct; unresolved periods are TBD-006. All investigation-owned records inherit ownership and expiration. A stale response cannot bypass those invariants.

### 3.6 Design constraints

#### CON-001 — Retained technology stack

The pilot shall retain the existing Python/FastAPI, plain HTML/JavaScript/CSS, SQLite, and Docker stack.

- Priority: Must
- Source: SRC-004
- Verification: Inspection
- Status: Approved
- Acceptance: Given the implementation plan, when reviewed, then a replacement framework/database is not required to deliver the approved pilot; additional services require explicit justification within budget.
- Traces: CMP-001, CMP-002, CMP-003, CMP-004, CMP-005, CMP-006

#### CON-002 — Monthly operating budget

The pilot shall be designed against a USD 25 total monthly operating allowance.

- Priority: Must
- Source: SRC-002
- Verification: Analysis
- Status: Approved
- Acceptance: Given actual provider entitlements, hosting measurements, and billable-job usage, when the cost model is reviewed, then the proposed operating envelope fits the allowance or reports a blocker before paid deployment.
- Traces: ENT-007, ENT-009, API-015, CMP-004, CMP-006

The proposed $7 hosting / $12 model / $3 search / $3 contingency allocation is planning, not an independently approved provider contract or measured cost. Entitlements, account-wide usage, taxes, and actual prices are TBD-001/TBD-002. An application admission rule cannot guarantee an external account's total bill.

#### CON-003 — Export-based pilot sharing

The pilot shall provide sharing through owner-initiated exports rather than public report hosting or in-app share links.

- Priority: Must
- Source: SRC-004
- Verification: Test, Inspection
- Status: Approved
- Acceptance: Given an exported report, when sharing is completed by the user, then no application-hosted anonymous access path is created.
- Traces: API-013, CMP-001, CMP-002

#### CON-004 — Supplied-material ingestion boundary

The pilot shall obtain research input from submitted text/transcript files rather than automated platform extraction or media transcription.

- Priority: Must
- Source: SRC-002, SRC-004
- Verification: Test, Inspection
- Status: Approved
- Acceptance: Given a YouTube/source URL reference, when saved, then no metadata, captions, audio, or page content is fetched as an ingestion side effect.
- Traces: ENT-003, API-006, CMP-003

### 3.7 Software system attributes

#### 3.7.1 Reliability

FR-016 and NFR-001 govern durable job outcomes and one executor. On ambiguous provider timeout, paid retries require their own reservation; an uncertain billed operation cannot be assumed free. Recovery design is ADR-004.

#### 3.7.2 Availability

No numeric SLA is approved. Provider outages and budget exhaustion are explicit research-unavailable states. Hosting availability and recovery objectives are TBD-003/TBD-006.

#### 3.7.3 Security

#### NFR-005 — Private-data access isolation

The system shall enforce owner authentication on every content-bearing API, file, export, and background-job action.

- Priority: Must
- Source: SRC-003; implementation details SRC-006
- Verification: Test
- Status: Approved scope
- Measure: Zero successful unauthenticated reads/mutations in the enumerated route/asset tests.
- Acceptance: Given unauthenticated, expired, or logged-out sessions, when any private resource is requested, then no investigation content is returned; mutation endpoints also reject requests lacking the required session-bound CSRF protection.
- Traces: ENT-001, ENT-002, API-001, API-002, API-014, CMP-002, CMP-006

Cookie/session, transport, uploaded-text rendering, prompt-injection boundaries, and secret handling are proposed mechanisms in Architecture §7.1. Authentication method is TBD-008.

#### 3.7.4 Maintainability

Existing lint, unit/service/integration, and browser-test layers are retained under CON-001. New tests must cover the actual private workflow; existing seeded video-browser tests are not live ingestion evidence. No numerical maintainability target was agreed.

#### 3.7.5 Portability

The existing container remains the deployment unit. Markdown and versioned JSON exports provide readable and structured portability under FR-013. Platform-specific authentication/storage decisions remain documented dependencies.

#### 3.7.6 Privacy and compliance

#### NFR-006 — Content-free operational diagnostics

The system shall exclude investigation text, evidence passages, search query text, credentials, and session tokens from operational logs and cost records.

- Priority: Must
- Source: SRC-003; details SRC-006
- Verification: Test, Inspection
- Status: Proposed design
- Measure: Zero prohibited fields in captured diagnostic/ledger output for import, success, errors, and deletion.
- Acceptance: Given a provider exception containing request material, when logged, then only redacted categories, counters, timing, and correlation identifiers appear.
- Traces: ENT-009, CMP-002, CMP-004, CMP-005

#### NFR-007 — Processing disclosure

The system shall disclose the enabled external processing and deletion limitations before the owner initiates paid processing.

- Priority: Must
- Source: SRC-003; details SRC-006
- Verification: Inspection, Demonstration
- Status: Approved scope; contract facts TBD-001/TBD-006
- Measure: Each enabled integration has a visible processing/retention description.
- Acceptance: Given extraction/research initiation, when the owner confirms it, then the interface identifies model processing and external-search disclosure; immediate application deletion is not represented as immediate provider or downloaded-copy deletion.
- Traces: ENT-007, API-008, API-011, CMP-001, CMP-005

#### 3.7.7 Observability

Job state, provider outcomes, duration, reservations, and known usage support FR-016–FR-018 and NFR-003. NFR-006 constrains their contents. External account charges are reconciled separately; unknown charges retain conservative reservations pending reconciliation.

### 3.8 Supporting information

Happy path: sign in -> create investigation -> declare eligibility/import -> inspect source -> extract candidates -> correct/select -> research -> inspect evidence -> edit/review -> export.

Required failure examples: malformed transcript; oversize text; unsupported file; empty candidate list; missing provider entitlement; pricing unknown; insufficient budget; provider failure; invalid citation; service restart; deletion during a job; expiration between selection and export. Files and provider text are untrusted content, not application instructions.

## 4. Verification

This documentation task did not run application verification and does not establish release readiness.

Implementation verification uses parser/citation unit tests, authenticated API/database integration tests, budget/concurrency/recovery tests, and a browser walkthrough of the private workflow. Test doubles verify deterministic failure behavior; separate permitted live-provider trials establish runtime behavior and billable cost. Representative researcher-reviewed material measures evidence relevance and preserved context; thresholds are TBD-003.

| Gate | Evidence required |
|---|---|
| Input/provenance | TXT/SRT/VTT/paste cases, cue times, exact source references, malformed and boundary inputs |
| Private access | Inventory of all routes/assets; unauthenticated and CSRF failure tests; no anonymous legacy content exposure in pilot deployment |
| Research integrity | Valid/invalid citations; contextual human review; contradictory/missing evidence and provider-failure cases |
| Budget and durability | One executor under concurrency; repeated/ambiguous request handling; deletion does not refund incurred usage |
| Retention/deletion | Expired reads refused; late responses cannot recreate deleted content; actual backup/provider limits disclosed |
| Export | Markdown/JSON same revision and review state; restricted evidence omitted; no hosted share link |
| Provider/operations | Resolved intended-use rights, authentication, actual prices/limits, byte limit, and deletion/recovery behavior |

Existing CI commands: `ruff check backend tests`; `pytest tests/unit tests/services tests/integration`; `pytest -m e2e tests/e2e` after installing Playwright Chromium. Future changed tests must be added to those layers. Provider/live trials are separate from seeded E2E.

## 5. Appendices

### 5.1 Traceability matrix

| Req | Priority | Entities | APIs / Events | Components | Verification |
|---|---|---|---|---|---|
| FR-001 | Must | ENT-001 | API-001–API-003 | CMP-001, CMP-002 | Test |
| FR-002 | Must | ENT-002 | API-004, API-005 | CMP-001, CMP-002, CMP-006 | Test |
| FR-003 | Must | ENT-003 | API-006, API-007 | CMP-001, CMP-002, CMP-003, CMP-006 | Test |
| FR-004 | Must | ENT-003 | API-006 | CMP-001, CMP-002, CMP-003 | Test |
| FR-005 | Must | ENT-003, ENT-004 | API-007, API-009 | CMP-003, CMP-006 | Test |
| FR-006 | Must | ENT-004, ENT-008 | API-008–API-010 | CMP-003, CMP-004 | Demonstration, Test |
| FR-007 | Must | ENT-004, ENT-008 | API-009, API-011 | CMP-001, CMP-002, CMP-004 | Test |
| FR-008 | Must | ENT-005, ENT-007 | API-011 | CMP-004, CMP-005 | Test, Inspection |
| FR-009 | Must | ENT-005, ENT-006 | API-012 | CMP-004, CMP-005 | Test |
| FR-010 | Must | ENT-005, ENT-006 | API-012 | CMP-001, CMP-004 | Demonstration, Test |
| FR-011 | Must | ENT-006 | API-012 | CMP-001, CMP-002, CMP-006 | Test |
| FR-012 | Must | ENT-004–ENT-006, ENT-008 | API-012 | CMP-004, CMP-006 | Test |
| FR-013 | Must | ENT-006, ENT-007 | API-013 | CMP-001, CMP-002, CMP-005 | Test |
| FR-014 | Must | ENT-002–ENT-006, ENT-008 | API-014 | CMP-002, CMP-004, CMP-006 | Test |
| FR-015 | Must | ENT-002 | API-005, API-014 | CMP-002, CMP-004, CMP-006 | Test |
| FR-016 | Must | ENT-008 | API-008, API-010, API-011 | CMP-001, CMP-002, CMP-004, CMP-006 | Test |
| FR-017 | Must | ENT-007–ENT-009 | API-008, API-011, API-015 | CMP-004, CMP-005, CMP-006 | Test |
| FR-018 | Must | ENT-009 | API-015 | CMP-004, CMP-006 | Test |
| NFR-001 | Must | ENT-008 | API-008, API-011 | CMP-004, CMP-006 | Test |
| NFR-002 | Must | ENT-003, ENT-008 | API-006, API-011 | CMP-003, CMP-004 | Test |
| NFR-003 | Should | ENT-008, ENT-009 | API-010 | CMP-004 | Analysis |
| NFR-004 | Must | ENT-006 | API-012, API-013 | CMP-001 | Demonstration, Test |
| NFR-005 | Must | ENT-001, ENT-002 | API-001, API-002, API-014 | CMP-002, CMP-006 | Test |
| NFR-006 | Must | ENT-009 | — | CMP-002, CMP-004, CMP-005 | Test, Inspection |
| NFR-007 | Must | ENT-007 | API-008, API-011 | CMP-001, CMP-005 | Inspection, Demonstration |
| IR-001 | Must | — | API-001, API-005, API-010, API-013 | CMP-002 | Test |
| IR-002 | Must | ENT-007 | API-011, API-013 | CMP-004, CMP-005 | Test, Inspection |
| CON-001 | Must | — | — | CMP-001–CMP-006 | Inspection |
| CON-002 | Must | ENT-007, ENT-009 | API-015 | CMP-004, CMP-006 | Analysis |
| CON-003 | Must | — | API-013 | CMP-001, CMP-002 | Test, Inspection |
| CON-004 | Must | ENT-003 | API-006 | CMP-003 | Test, Inspection |

### 5.2 Open issues (TBD)

| TBD | Question | Assumption used | Affects | Owner |
|---|---|---|---|---|
| TBD-001 | Which actual provider entitlements allow processing, persistent reports/excerpts, citations, and user export; what are their prices and limits? | Integrations disabled until a useful complete intended-use policy is established; existing keys prove neither rights nor availability | FR-008, FR-013, IR-002, CON-002 | Owner/operator |
| TBD-002 | What are measured hosting/job costs, account billing boundaries, and monthly report volume? | USD 25 allowance; proposed allocation in §3.6; no promised report count | CON-002, FR-017, FR-018 | Owner/operator |
| TBD-003 | Which measured quality, time-saved, latency, and availability thresholds define pilot success? | Evaluate representative jobs; deterministic integrity gates apply; empirical targets deferred | NFR-003, §4 | Owner/researcher |
| TBD-004 | Which topics, languages, and representative research corpus should the pilot evaluate? | Preserve supplied text/language; do not promise coverage before evaluation | FR-006, FR-010, §4 | Owner/researcher |
| TBD-005 | What upload-byte/token limits and UTF-8/markup handling bounds fit available resources? | Word/claim limits approved; reject unsafe/unbounded inputs; numeric transport bound unresolved | FR-003, NFR-002, API-006 | Implementer/operator |
| TBD-006 | What backup purge, content-free ledger/session retention, provider deletion limits, and recovery objectives are acceptable? | Immediate active-content deletion; fixed investigation expiry; no external immediate-deletion guarantee; ledger persists for current budget reconciliation | FR-014, FR-015, FR-018, NFR-007 | Owner/operator |
| TBD-007 | Which supported browsers and accessibility standard should be required? | Desktop browser pilot; numeric/standards targets not invented | §1.3.2, §3.3, §4 | Owner/implementer |
| TBD-008 | Which owner authentication mechanism and recovery process fit the budget/deployment? | Server-validated private session; no public registration; choice unresolved | FR-001, NFR-005, API-001 | Owner/operator |

TBD-001, TBD-005, TBD-008, and the deletion/retention portions of TBD-006 need concrete decisions before enabling affected deployed workflows. Cost feasibility must be demonstrated before paid deployment. Other empirical targets remain visible evaluation decisions; they must not be silently marked passed.

### 5.3 Acronyms, abbreviations, and definitions

| Term | Definition |
|---|---|
| Investigation | Owner's private research case with a fixed expiration deadline |
| Reviewed | Researcher explicitly reviewed a particular report revision; not a certification of truth |
| Evidence | Retrieved material with identified provenance and recorded use permission |
| Source document | User-supplied immutable text/transcript representation |
| SRT / VTT | Timestamped subtitle formats; no video/audio acquisition implied |
| Reservation | Conservative funds withheld before an operation; not an invoice or guaranteed maximum external-account charge |
| Immediate deletion | Active application content removal at successful deletion response; limitations for providers/backups/downloads disclosed |

## Revision history

| Rev | Date | Commit | Mode | Summary |
|---|---|---|---|---|
| 1 | 2026-10-14T12:40:45-04:00 | uncommitted | INIT | Initial approved pilot scope; FR-001–FR-018, NFR-001–NFR-007, IR-001–IR-002, CON-001–CON-004; eight explicit TBDs; documentation-only authorization |
