# YouTube Fact Checker

Paste a YouTube URL and get AI-powered fact-checking of every claim the creator makes.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

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
- **LLM**: Anthropic Claude Haiku
- **Search**: Brave Search API
- **Frontend**: Vanilla HTML/CSS/JS
- **Transcript**: youtube-transcript-api

## Limitations

- Only works with videos that have captions (auto-generated or manual)
- Speaker identification is approximate (uses LLM filtering, not audio diarization)
- Truth scores are AI estimates, not definitive verdicts
- Rate-limited by API quotas (Brave: 2000/month free, Anthropic: pay-per-use)
