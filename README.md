# YouTube Fact Checker

Paste a YouTube URL and get AI-powered fact-checking of every claim the creator makes.

See [Hosting without Railway](docs/hosting.md) for Render Free deployment,
durable Postgres storage, and importing an existing SQLite database.

## Quick Start

### 1. Install dependencies

Install Python 3.11+ and Rust/Cargo 1.85+ (CI uses Rust 1.93.1). Build the required
native processor once before starting the backend:

```bash
pip install -r requirements.txt
python scripts/build_native.py
```

Rebuild and restart the backend after changing `native/`. The Docker build compiles
and includes the library automatically; Rust is not needed in the running container.

### 2. Set up API keys

Copy `.env.example` to `.env` and add your keys:

```bash
cp .env.example .env
```

You need:
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **Brave Search API key** — [api.search.brave.com](https://api.search.brave.com)

### 3. Run the app

```bash
python -m backend.main
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## How It Works

1. You paste a YouTube URL (videos under 10 minutes)
2. The app extracts the video's transcript using YouTube captions
3. Claude (Haiku) identifies factual claims from the transcript
4. Each claim is searched on the web via Brave Search
5. Claude evaluates the evidence and assigns a truth percentage (0-100%)
6. Results are displayed with an overall accuracy score

## Tech Stack

- **Backend**: Python / FastAPI
- **Validation and normalization**: Rust shared library, loaded in process with Python's `ctypes`
- **LLM**: Anthropic Claude Haiku
- **Search**: Brave Search API
- **Frontend**: Vanilla HTML/CSS/JS
- **Transcript**: youtube-transcript-api

The Rust processor handles LLM JSON/fence parsing, claim normalization and timestamp
clamping, YouTube URL/ID validation, transcript filtering, and timestamp formatting.
Caption batches cross the native boundary in one call. FastAPI, provider requests,
fact scoring, storage, and the frontend remain Python/JavaScript. A missing or
incompatible native library fails at startup with rebuild instructions.

Supported URLs include HTTP(S) watch, short, embed, shorts, and `/v/` URLs on known
YouTube hosts, schemeless equivalents, and exact 11-character video IDs. Lookalike
hosts, embedded URLs, duplicate `v` parameters, and longer ID prefixes are rejected.
Claims keep their input order and repetitions; captions keep repeated rows too.
Wrong-type claim text is dropped, invalid categories default to `fact`, and claim
text is truncated at 500 Unicode code points plus an ellipsis. Transcript rows with
missing/wrong-type text or invalid/non-finite times are skipped; negative caption
times are clamped to zero. Video duration must be finite and positive.

JSON parsing retains the outermost-fragment fallback in first-start order. Two
adjacent structures of the same kind are not treated as one valid response. The
native boundary accepts at most 8 MiB per batch, uses a 128-level nesting
limit, and rejects non-standard JSON numbers (`NaN`/`Infinity`) and invalid Unicode
surrogates. Empty or unparseable claim output returns an empty claim list.

## Tests

```bash
cargo fmt --manifest-path native/Cargo.toml --check
cargo test --locked --manifest-path native/Cargo.toml
cargo clippy --locked --manifest-path native/Cargo.toml --all-targets -- -D warnings
python scripts/build_native.py
pytest tests/unit tests/services tests/integration
```

These backend tests use synthetic data, temporary databases, and mocked provider
responses. They do not load `.env` or permit external network connections. For the
optional Postgres storage contracts, explicitly set `TEST_DATABASE_URL` to an
isolated test server. Browser E2E tests are separate and are not part of this command.

## Limitations

- Only works with videos that have captions (auto-generated or manual)
- Speaker identification is approximate (uses LLM filtering, not audio diarization)
- Truth scores are AI estimates, not definitive verdicts
- Rate-limited by API quotas (Brave: 2000/month free, Anthropic: pay-per-use)
