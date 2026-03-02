# AIContentEngineVersion2

Autonomous weekly tweet pipeline that scrapes tech/AI news from RSS feeds, ranks stories, and tweets the top 5 every Friday via X API v2.

## How It Works

1. **Ingest** — Fetches 7 RSS feeds (OpenAI, Anthropic, Google AI, Meta AI, Hugging Face, Mistral, EU AI Act) and stores items in SQLite
2. **Process** — Deduplicates (fuzzy matching), embeds (MiniLM), clusters (agglomerative), and scores stories
3. **Tweet** — Posts the top 5 stories to X/Twitter

Runs weekly via GitHub Actions (Fridays 09:00 UTC) with no human input required.

## Scoring

```
score = 25 × source_weight + 15 × recency + 20 × practical
```

- **source_weight**: from sources.yaml (OpenAI=1.2, Anthropic/EU=1.1, others=1.0)
- **recency**: `max(0, 1 - days_old/7)` — 1.0 if today, 0.0 if 7+ days
- **practical**: 1.0 if title/text contains action keywords, 0.6 otherwise

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd AIContentEngineVersion2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure X API credentials

Copy `.env.sample` to `.env` and fill in your X API v2 credentials:

```bash
cp .env.sample .env
```

To get X API keys:
1. Go to https://developer.x.com/en/portal/dashboard
2. Create a project and app (Free tier works)
3. Generate API Key & Secret, Access Token & Secret
4. Ensure your app has **Read and Write** permissions

### 3. Test locally

```bash
# Fetch RSS feeds
python scripts/ingest.py

# Process and rank stories
python scripts/process.py

# Preview tweets (no posting)
python scripts/tweet.py --dry-run

# Post for real
python scripts/tweet.py
```

### 4. Deploy to GitHub Actions

1. Push to GitHub
2. Add 4 repository secrets: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`
3. Trigger manually via Actions → Weekly Tweet Pipeline → Run workflow, or wait for Friday 09:00 UTC

## Project Structure

```
├── .github/workflows/weekly.yml   # Cron schedule
├── configs/sources.yaml           # RSS feed sources + weights
├── scripts/
│   ├── ingest.py                  # RSS → SQLite
│   ├── process.py                 # Dedupe → cluster → score
│   └── tweet.py                   # Top 5 → X API v2
├── lib/
│   ├── db.py                      # SQLite schema + connection
│   ├── twitter.py                 # Tweet formatting + truncation
│   └── settings.py                # Config via env vars
├── data/                          # SQLite DB (gitignored)
└── requirements.txt
```
