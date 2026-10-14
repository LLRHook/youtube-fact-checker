# YouTube Fact Checker

This repository contains the existing YouTube-based fact checker and the approved plan for a private research workbench. The new pilot is groomed and ready for its first implementation ticket; its features are not yet implemented or deployed.

[![CI](https://github.com/LLRHook/youtube-fact-checker/actions/workflows/ci.yml/badge.svg)](https://github.com/LLRHook/youtube-fact-checker/actions/workflows/ci.yml)

![Fact-check report on desktop](docs/images/report-desktop.png)

## Product direction and implementation status

The current code is the legacy YouTube-based application described below. The approved next pilot is a **private research workbench** for one authenticated researcher using authorized non-confidential pasted text and TXT/SRT/VTT files. The workbench and UI overhaul are planned, not implemented or deployed. A reachable health endpoint does not establish working ingestion or research.

- [Requirements](docs/SRS.md), [Data Contracts](docs/DATA_CONTRACTS.md), [Architecture](docs/ARCHITECTURE.md).
- [Approved UI overhaul](docs/UI_OVERHAUL.md), [groomed implementation order](docs/GROOMING.md).
- [Feature tickets](features.md), [bug tickets](bugs.md), [verification procedure](VERIFICATION.md), [changelog](CHANGELOG.md).
- [Product feasibility](docs/PRODUCT_FEASIBILITY.md) and [evidence-provider constraints](docs/EVIDENCE_PROVIDER_FEASIBILITY.md).

The pilot uses private reports and explicit Markdown/JSON exports, fixed 30-day investigation retention, a USD 25 monthly operating envelope, and one executing paid job. Provider licenses/prices and measured operating/quality limits remain gates to live research and release. Network/proxy access is not proof of terms-compliant acquisition.

## Existing application features

- Claim extraction with check-worthiness ranking.
- Brave LLM Context evidence and Google Fact Check results.
- Reliability-ranked sources.
- Seven-point verdicts with quote-verified citations.
- Live processing progress and claims as they are checked.
- Saved report pages with timestamp seeking in the video player.
- Browse and channel pages.
- Feedback on individual assessments.
- Cost tracking and a daily processing budget.

## How it works

```text
YouTube URL -> timestamped transcript -> claim extraction
    -> Brave LLM Context + Google Fact Check -> evidence-based verdicts
    -> citation checks + summary -> SQLite -> live progress / saved report
```

## Accuracy safeguards

- Grounding check: cited quotes must match the retrieved evidence; invalid and duplicate citations are dropped.
- Unverifiable over guessing: a checkable verdict without valid citations or declared general knowledge becomes unverifiable with low confidence.
- General-knowledge cap: uncited assessments based on general knowledge have at most medium confidence.
- Low-reliability cap: assessments citing only low-reliability sources have low confidence.
- Prompt-injection guard: the model is instructed to ignore instructions inside untrusted evidence.
- Refusal fallback: model refusals return an unverifiable assessment instead of a guessed verdict.

## Cost

Per video, roughly $0.30-0.60 with Claude Sonnet 5.5 and Brave Search, depending on claim count; set `DAILY_BUDGET_USD` to bound daily processing spend.

## Quick start

Use Python 3.13. On Windows, from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Add your provider keys to `.env`, then start the server:

```powershell
uvicorn backend.main:app --reload
```

Open [localhost:8000](http://localhost:8000). For a seeded demo, run this before starting the server:

```powershell
python scripts/seed_demo.py data/demo.db
$env:DATABASE_PATH = "data/demo.db"
uvicorn backend.main:app --reload
```

## Configuration

See [.env.example](.env.example) for all settings and defaults.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude claim extraction, verdicts, and summaries |
| `BRAVE_API_KEY` | Web evidence retrieval |
| `GOOGLE_FACTCHECK_API_KEY` | Google Fact Check retrieval |
| `VERDICT_MODEL` | Model used to assess claims |
| `DAILY_BUDGET_USD` | Daily processing budget; excess work is queued |
| `MAX_VIDEO_DURATION_SECONDS` | Maximum accepted video duration |
| `TRANSCRIPT_PROXY_URL` | Proxy for transcript and video metadata access |

The legacy pipeline exposes `TRANSCRIPT_PROXY_URL`, but network/proxy access does not establish permission to acquire content. The approved pilot uses supplied text/transcript files and does not depend on automatic YouTube extraction; see the provider feasibility and SRS documents.

## Tests

```powershell
ruff check backend tests scripts
pytest tests/unit tests/services tests/integration -q
python -m playwright install chromium
pytest -m e2e tests/e2e -q
python scripts/screenshots.py
```

The browser tests and screenshot script start an isolated server with seeded reports. If system temp is blocked, use `--basetemp=.pytest_tmp` for pytest.

## Deployment

Build the Docker image or deploy it on Railway. Mount a persistent volume and set `DATABASE_PATH` to a database file on that volume. The container honors `PORT` (default `8000`); `/api/health` is the health check endpoint. Configure provider keys and the daily budget in the deployment environment.

## Limitations

- Videos need accessible captions and must fit the configured duration limit.
- Caption errors and approximate speaker attribution can affect extracted claims.
- Verdicts are automated evidence assessments; read the cited sources before relying on them.
- Search coverage, provider quotas, and network access affect evidence quality and processing availability.
- Prompt instructions and citation checks reduce errors but cannot eliminate them.

## The cycle-file contract

Use `features.md` and `bugs.md` for working tickets; `docs/GROOMING.md` records dependencies and initial readiness. New IDs use real UNIX epoch seconds (`FEAT-<epoch>` / `BUG-<epoch>`), never sequential counters. Append at the end of `## Open`; preserve every ID and archive. Status changes are in place. The three trackers/ledger use `merge=union`.

The development cycle is `/groom` -> `/implement` or explicitly authorized `/implement-batch` -> `/protocol-v-and-v` -> `/release`. Ticket filing is not permission to deploy. After implementation, add the Implementation/Fix and Docs notes, tick only verified work, and set its pending-migration status. Only a full successful protocol run migrates completed tickets and appends a Verified entry. `CHANGELOG.md` is append-only; `VERIFICATION.md` contains procedure/current baselines, while ignored `.vv/` holds local run reports and backups.

No pilot implementation, release, merge, or production change was performed by this planning/bootstrap work. Begin with the first ready ticket named in `docs/GROOMING.md`; keep live provider enablement blocked until its actual permissions and cost facts are established.
