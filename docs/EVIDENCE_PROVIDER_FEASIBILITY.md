# Evidence-provider feasibility

Checked: 2026-10-14. Scope: Brave Search / LLM Context, Google Fact Check Tools, and Anthropic commercial API handling of transcripts and evidence. Primary sources only; no authenticated provider account, contract, API response headers, or production configuration inspected. This is a product-planning assessment, not a legal clearance.

## Decision-relevant findings

The evidence-retrieval and LLM portions are technically feasible through documented APIs. A reliable product still needs an explicit rights model for evidence stored in caches and reports. Changing video ingestion alone does not resolve that issue. Public documentation demonstrates capability; the actual subscription agreement and content permissions determine permitted use.

Accepted audience: researchers/journalists reviewing supplied material; the user accepts changing the automatic YouTube URL workflow. Confirmed pilot: one authenticated user; authorized public/non-confidential text, scripts and TXT/SRT/VTT inputs; private reports with explicitly initiated export/sharing; 30-day application retention and immediate user deletion; Markdown/JSON exports; USD 25 monthly operating budget (interpretation of the answer "25"). Private use does not waive API caching, derivative-work or content-copy restrictions. Downloadable evidence bundles and report exports need explicit consideration alongside server storage. Account-specific entitlements, provider deletion exceptions and actual usage remain unverified.

### Brave Search and LLM Context

**Technical capability.** LLM Context supplies extracted page chunks and source metadata for model consumption, including fact checking and RAG. It supports GET/POST with an API key, configurable token/URL budgets, and relevance filtering. Its documentation mentions YouTube captions as one possible retrieved content type; this is not a promised arbitrary-video transcript API or a grant from YouTube. July 2026 changes mean snippet-count limits are no longer necessarily binding when the token budget allows more snippets. [LLM Context documentation](https://api-dashboard.search.brave.com/documentation/services/llm-context).

**Contract restrictions.** General terms, updated September 1, 2026, permit application use of results but restrict caching/database creation beyond transient operational storage. They also restrict derivative works, result redistribution/resale, and AI model/service creation, evaluation, training or improvement. An Order Form can add terms. Attribution is optional; if elected, it requires conspicuous prescribed wording and logo or written approval. End users need substantially similar written obligations and required privacy notices/consents. [Brave API terms, §§2–4](https://api-dashboard.search.brave.com/terms-of-service).

**Storage and third-party rights.** Brave's FAQ says storing any portion of results requires a plan expressly granting storage rights. Such permissions are outside its general terms. It also says API access grants no rights to third-party webpages; access must respect publisher copyright terms. A paid API key alone does not establish these storage permissions. [Brave API FAQ](https://brave.com/search/api/).

**Inference versus training.** Brave explicitly describes feeding search results to models at inference time. That supports ordinary grounding as an intended product capability, but it does not waive specific caching, saved-report, derivative-work or training restrictions. [Brave inference guide](https://brave.com/search/api/guides/using-brave-search-api/).

**Unresolved / implementation implications.** Obtain the exact subscription entitlement or written clarification for persistent passages, report quotations, saved AI conclusions and citations. Treat the general derivative-work clause and the documented inference use as a scope question requiring reconciliation, not a blanket ban on inference. Default to job-lifetime evidence processing until confirmed; disabling raw-result caching alone does not establish rights for permanent reports. No account-specific clearance was found in this research.

### Google Fact Check Tools

**Technical capability and prerequisites.** Claim Search requires an API key and searches the fact-check corpus available through Fact Check Explorer. ClaimReview read/write is a separate capability requiring Search Console authorization for the publisher's site; those requirements are not prerequisites for read-only Claim Search. Both are subject to Google's API terms. The documentation page's CC BY / Apache footer covers that page and its code samples, not automatically publisher articles or every returned claim. [Getting started](https://developers.google.com/fact-check/tools/api/).

The text endpoint returns matching claims and associated reviews, with text/language/publisher/age filters and pagination. It retrieves existing fact checks rather than deciding the truth of a newly submitted claim. [Claim Search reference](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search).

**Contract restrictions.** Google API terms do not transfer ownership of returned content. Unless permitted by its owner or applicable law, they prohibit permanent copies/databases, caches beyond response cache-header permission, and copying/modification/public display/distribution. Source and author notices must not be misrepresented or removed. API-specific documented attribution applies; branding must not imply endorsement. Additional API terms control conflicts. [Google API terms, §§1, 3, 5–6](https://developers.google.com/terms).

**Unresolved / implementation implications.** No blanket publisher-content license or Fact Check-specific persistent-storage exception was established. Inspect successful authenticated response cache headers before setting a cache duration. Preserve publisher identity, original rating, review date and link when permitted, while distinguishing their verdict from the application's assessment. Matching the topic alone does not establish the same proposition, time or scope. The current source cache does not record cache headers. No live API calls were made, so quota/access and actual cache policy remain unverified.

### Anthropic commercial API

**Contract requirements.** Commercial terms permit powering customer products, give the customer rights in outputs as between the parties, require necessary rights/permissions for submitted inputs, and incorporate a DPA. They require evaluating outputs before sharing and notifying users that factual assertions need independent accuracy checks. Output ownership does not cure missing rights in submitted transcripts or publisher material. [Commercial terms, §§A–D, L.1](https://www.anthropic.com/legal/commercial-terms).

**Training.** Commercial inputs and outputs are not used for model training by default. Explicit feedback, bug submissions or opting in can change that; feedback can retain the associated conversation for five years. [Commercial training policy](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training).

**Retention.** Standard API input/output deletion is within 30 days, with exceptions for features such as Files API, contractual arrangements, law and safety enforcement. Flagged inputs/outputs can be retained up to two years and safety classifications up to seven years. Do not promise immediate deletion or universal zero retention. [Commercial retention policy](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data).

**Model-specific uncertainty.** Covered-model rules can require retention even for otherwise ZDR organizations, with some eligibility exceptions. Recheck the chosen model/workspace before promising ZDR. This research does not establish that the project's configured model is covered. [Covered-model retention](https://privacy.claude.com/en/articles/15425996-data-retention-practices-for-covered-models).

## Local implementation evidence

Inspected branch `feat/v2-upgrade`, HEAD `728ff5b59e8e50f486af19fbcbaf3013deb512c3`; working tree was clean at intake.

| Behavior | Code evidence | Planning consequence |
| --- | --- | --- |
| Both providers serialize complete `SearchResult` objects, including passages, into SQLite | `backend/services/search_service.py:76–86`, `:188`, `:230` | Both need provider-specific storage policy |
| Default cache lifetime is 14 days | `backend/config.py:30` | A local TTL is not contractual permission |
| Cache reads use application age, not HTTP cache headers | `backend/database.py:552–560` | Google cache permissions currently are not enforced |
| Report sources have persistent snippet fields | `backend/database.py:79–84`, `:373–395` | Audit saved quotations separately from search cache |
| Google results synthesize snippets with claim text, claimant and rating | `backend/services/search_service.py:207–220` | These are still copies of returned content, despite formatting changes |

No code, accounts, deployments or contracts were changed. Verification: reviewed cited official documents and local implementation; runtime provider reliability and account entitlements remain unverified. Only this research note is the delegated deliverable.

## Next concrete requirements

1. Choose evidence providers whose written terms cover inference, private report storage, user exports, citations and limited quotations; capture plan entitlements and termination/deletion obligations.
2. Separate job-only raw evidence from persistent report data, with a policy per provider/content license. Confirm whether report conclusions and citation metadata also fall under provider restrictions.
3. Add provenance and retention metadata, and preserve each professional fact-checker's original rating and attribution when authorized.
4. State Anthropic processing in product privacy terms, obtain necessary submission rights, and align application deletion promises with provider retention.
5. Test coverage and claim matching against a small representative corpus before making accuracy promises. Successful retrieval alone cannot establish that a claim is true or false.
