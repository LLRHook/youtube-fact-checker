# Product feasibility: research and evidence workbench

Checked: 2026-10-14. Status: feasibility findings and proposed scope, not an approved implementation specification.

## Decision context

The user wants the idea to work reliably while following source-platform terms. The first audience is **researchers and journalists reviewing supplied material**. The user accepts changing the original automatic YouTube URL workflow.

Confirmed pilot decisions:

- Inputs: pasted text, scripts, TXT, SRT, and VTT files; media inputs later.
- Access: just the owner initially, with authenticated private access.
- Material: public or non-confidential material the user is authorized to process.
- Reports: private by default; export or sharing must be explicitly initiated by the researcher.
- Retention: investigations kept for 30 days; immediate user deletion from the application. External-provider and backup deletion timelines must be disclosed separately.
- Exports: Markdown and structured JSON evidence files.
- Budget: the user's answer "25" is interpreted as USD 25 total monthly operating budget. Expected report volume was not supplied.

Recommendation: retain the claim-research idea and useful code, and replace automatic YouTube extraction as the core input. Start with material supplied through an authorized route and produce a research dossier that a person reviews. Treat YouTube links as optional references. Do not promise a definitive truth percentage for a video or creator.

This memo distinguishes documented API capabilities, contract restrictions, engineering recommendations, and unresolved permission questions. It does not establish that a particular customer agreement or legal exception authorizes a use.

## What the official YouTube routes provide

| Route | Documented capability or restriction | Product consequence |
|---|---|---|
| Automatic extraction from an arbitrary public video | General terms restrict automated access and interference with restrictions; API policies prohibit scraping and undocumented APIs. | The existing scraper is not a defensible default for the user's stated terms-compliance goal without an applicable permission route. |
| Public metadata via `videos.list` | Returns selected video-resource fields, including metadata and duration; this is not transcript retrieval. | An optional integration can fetch metadata through the official API without solving content ingestion. |
| Captions via OAuth | `captions.list` returns track information, not caption text. `captions.download` requires an authorized user with permission to edit the video. | Signing in as a viewer does not grant access to another creator's captions. Creator integration is technically possible where permissions and tracks exist. |
| Creator supplies their own file | YouTube Studio supports downloading caption files and uploaded videos. | Prefer the creator's original script/file or an authorized export; obtain the necessary rights for our own processing. |
| Standard embedded playback | The IFrame API supports player controls and playback. | Playback is a viewing feature, not permission or an API for extracting audio and transcribing it. |

Sources: [YouTube general terms, Permissions and Restrictions](https://www.youtube.com/static?template=terms&gl=US&hl=en); [Developer Policies, III.E.6 and III.D.7](https://developers.google.com/youtube/terms/developer-policies); [videos.list](https://developers.google.com/youtube/v3/docs/videos/list); [captions.list](https://developers.google.com/youtube/v3/docs/captions/list); [captions.download](https://developers.google.com/youtube/v3/docs/captions/download); [Studio caption exports](https://support.google.com/youtube/answer/2734705?hl=en); [uploaded-video exports](https://support.google.com/youtube/answer/56100?hl=en); [IFrame API](https://developers.google.com/youtube/iframe_api_reference).

### Important permission distinctions

A proxy can change network accessibility; it does not itself grant permission. A third-party transcript service must establish its authority to obtain and license the material. Its API availability or marketing claim alone is not sufficient. Moving extraction into a browser extension does not itself solve permission.

API policies constrain derived data and public aggregation. There is a newer, approval-dependent analytics amendment, but it does not establish that our factual assessments of API captions are approved. The applicability of that amendment to this use is unresolved. Independently supplied material should have separate provenance from platform API data. [Developer Policies, III.E and III.L](https://developers.google.com/youtube/terms/developer-policies), [additional analytics policies](https://developers.google.com/youtube/terms/derived-metrics-policy).

The academic Researcher Program offers expanded metadata access and has institution/publication eligibility conditions. It is not evidence of an arbitrary-video transcript license or a commercial journalist-product route. [Program scope](https://research.youtube.com/how-it-works/), [eligibility](https://www.research.youtube/policies/).

## Viable product directions

| Direction | Input | Assessment |
|---|---|---|
| Research workbench | Researcher's notes, original scripts, authorized transcript files, permitted excerpts or licensed documents | Recommended first version for the chosen audience. Removes YouTube extraction from the critical path. |
| Creator review tool | Creator's scripts, original media, caption exports | Also viable as a later use case; original files avoid reliance on platform caption availability. |
| Creator-connected YouTube analysis | Official OAuth captions where the user can edit the video | Conditional extension. Needs an actual permitted-use review, OAuth/privacy requirements, and a real caption download test. |
| Any public YouTube URL, full automatic analysis | Scraped content or content received from a supplier | Do not promise this until rights, acquisition authority, downstream use, and reliability are established. |

User-supplied content is not automatically authorized. Record how it was obtained and the applicable ownership, license, permission, or other lawful basis. Avoid instructing users to scrape or download someone else's videos. A manually pasted whole transcript is not a blanket workaround.

For US use, criticism, news reporting, and research can be relevant to fair use, but the assessment is contextual. Copyright permissions and platform contract permissions are separate questions. There is no universal permitted quotation length or guaranteed research exemption. [US Copyright Office fair-use guidance](https://www.copyright.gov/fair-use/).

## Proposed first-release workflow

Input, access, privacy, retention, and export defaults above are confirmed. The following detailed workflow remains proposed pending the requirements summary:

1. Create a private investigation and add supplied text or a transcript, with source/provenance and a confidentiality classification.
2. Extract candidate claims while preserving their exact source passages, location, date, attribution, and context.
3. Let the researcher correct and select claims before spending money on research.
4. Find primary evidence and relevant professional fact checks through authorized APIs. Search for contradictory evidence as well as supporting material.
5. Produce an evidence table with source links, publication/access dates when available, quotations permitted for the use, scope limitations, and an AI-proposed assessment.
6. Let the researcher inspect sources, edit conclusions, add notes, and approve a report for export or explicit sharing.

The draft assessment should distinguish supported, contradicted, mixed/context-dependent, insufficient evidence, and non-factual/opinion claims. Keep the original statement visible when the model rewrites a claim. Do not infer a creator's overall credibility from a selected set of claims. Display AI-generated suggestions as drafts.

Methodology reference: the IFCN principles emphasize inspectable sources, suitable primary evidence, supporting and undermining evidence, transparent methods, and corrections. This is a design reference, not a claim of IFCN certification. [IFCN commitments](https://ifcncodeofprinciples.poynter.org/the-commitments).

## What is needed to make this useful and operable

| Area | Proposed requirement or decision to settle |
|---|---|
| Input | Text, TXT/SRT/VTT first is the lowest-dependency pilot. Audio/video uploads add transcription, temporary media storage, and additional privacy/cost decisions. |
| Identity and access | Private investigations require authenticated access or a deliberately limited single-user deployment. Existing anonymous public report routes are not an appropriate privacy boundary. |
| Evidence rights | Confirm the actual search-provider plan permits inference, excerpts, storage, and export. Treat each publisher's content rights separately. See the provider memo. |
| Confidentiality | Explain which material goes to the model provider, which claim text goes to external search, and provider retention. Support redaction or a no-external-search workflow before accepting confidential sources. |
| Provenance | Preserve source-file identity/version, locations, acquisition basis, evidence provenance, retrieval time, model/prompt version, and researcher revisions. |
| Retention | Agree on input/evidence/report retention and implement deletion for the database, uploaded files, logs, and backups. API metadata needs its own applicable refresh/delete policy. |
| Failure behavior | Evidence-provider failure must remain distinguishable from insufficient evidence. No successful-looking report when ingestion or research failed. |
| Cost | User selects claims; limit document size/claim count; show estimated and actual usage; enforce a monthly/daily cap based on the agreed budget. |
| Evaluation | Use researcher-labeled cases to measure claim/context preservation, evidence relevance, citation correctness, contradictions, and time saved. Thresholds must be agreed before launch. |

## Existing code worth keeping, with limits

The stack is Python 3.13, FastAPI, plain HTML/JavaScript/CSS, SQLite, Docker, Anthropic, Brave Search, and Google Fact Check tools. Railway serves the existing public site. The code can be reused selectively; deletion or a full rewrite is not required to test the new direction.

- Claim extraction: `backend/services/claim_extractor.py`; currently shaped around video transcripts. Generalize source locations and metadata after input scope is agreed.
- Evidence research: `backend/services/search_service.py`; existing APIs are useful, but saved passages/cache rights need verification.
- Citation validation: `backend/services/fact_checker.py`; currently checks quote fragments against retrieved titles/snippets, not necessarily a complete publisher page. A matching snippet does not establish that the conclusion is correct or contextually supported.
- Pipeline, cost tracking, and report rendering: reusable concepts, currently coupled to video IDs/public routes.
- Tests: CI runs `ruff check backend tests`, `pytest tests/unit tests/services tests/integration`, and Playwright `pytest -m e2e tests/e2e`. The E2E setup seeds reports and blocks YouTube browser requests. Those tests do not prove live ingestion works.

## Validation sequence before broader rebuilding

1. Choose input formats, private/shared behavior, budget, pilot volume, and confidentiality scope.
2. Verify provider permissions for the exact processing/storage/export workflow using the actual subscription terms. Do not substitute a public pricing label for contractual rights.
3. Build a small complete slice: supplied input -> researcher-selected claim -> evidence -> reviewed private report.
4. Trial representative material with researchers, including ambiguous claims, dated facts, conflicting evidence, missing sources, prompt injection, and provider failures.
5. Assess measured quality, researcher time saved, and cost. Expand inputs or add YouTube integration only after that evidence supports it.

Open decisions: evidence provider plan/rights; measurable acceptance targets; input and per-job limits; precise in-app sharing scope; expected report volume. No implementation, deployment, purchase, or removal of existing work has been performed for this feasibility review.

## Budget feasibility for the confirmed USD 25 limit

Proposed allocation, not observed production usage:

| Category | Monthly allowance |
|---|---:|
| Hosting and persistent storage | $7 |
| Model usage | $12 |
| Search usage | $3 |
| Contingency, including small overages/taxes | $3 |
| Total | $25 |

Railway Hobby has a $5 monthly minimum with $5 of usage included; actual usage above that is additional. The $7 hosting allowance must be checked against the deployed service's measured resource use. [Railway plans](https://docs.railway.com/pricing/plans).

The existing Claude Sonnet 5.5 model is published at $2 per million base input tokens and $10 per million output tokens. Illustrative arithmetic: 50,000 input tokens and 8,000 output tokens cost $0.18 at those base rates. That is not a measured report cost and excludes cache-write premiums, additional requests and retries. [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Brave publishes Search at $5 per 1,000 requests; 20 requests would cost $0.10 before credits. The published monthly credits are not needed for this estimate. An entitlement granting the required storage/report/export rights may have different pricing and is not established here. [Brave pricing](https://brave.com/search/api/), [Brave subscription pricing documentation](https://api-dashboard.search.brave.com/documentation/pricing).

At those illustrative token/request assumptions, a report costs $0.28 in variable model/search usage. Input length, repeated context, claim count and retries can change that materially. Do not promise a report count until representative jobs have been measured and required contract rights are priced.

Engineering consequence: meter both providers, reserve a bounded job budget before external calls, cap paid retries, and refuse additional research when the variable allowance is exhausted. Keep manual review and authorized existing-report exports usable when research is paused. Configure provider/hosting limits separately; the application cannot cap an entire external account's unrelated consumption or guarantee an exact final bill. [Railway cost controls](https://docs.railway.com/pricing/cost-control).
