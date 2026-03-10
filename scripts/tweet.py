"""Pick top 5 stories, generate 2-tweet threads via Claude, write to out/YYYY-MM-DD/."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from lib.db import get_db, init_db
from lib.twitter import twitter_length, twitter_truncate

HASHTAGS = "#AI #Tech"
MODEL = "claude-haiku-4-5"


def get_top_stories(conn, limit: int = 5) -> List[dict]:
    rows = conn.execute(
        "SELECT title, url, full_text, score FROM stories ORDER BY score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_tweet_thread(title: str, text: str, client: anthropic.Anthropic) -> Tuple[str, str]:
    """Use Claude Haiku to write a 2-tweet thread. Returns (tweet1, tweet2)."""
    prompt = f"""Write a 2-tweet thread about this AI news story.

Rules:
- Tweet 1: The main news — what happened and why it matters (max 220 characters)
- Tweet 2: A key detail, implication, or example that adds value (max 220 characters)
- Plain English, no jargon
- No hashtags, no URLs
- Separate the two tweets with exactly "---" on its own line
- Return only the two tweets, nothing else

Title: {title}
Full story: {text[:3000]}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    parts = [p.strip() for p in raw.split("---")]

    tweet1 = parts[0] if parts else title
    tweet2 = parts[1] if len(parts) > 1 else ""

    # Hard cap as safety net
    if len(tweet1) > 220:
        tweet1 = tweet1[:219] + "…"
    if len(tweet2) > 220:
        tweet2 = tweet2[:219] + "…"

    return tweet1, tweet2


def format_thread(story: dict, client: anthropic.Anthropic) -> Tuple[str, str]:
    title = story["title"] or "Untitled"
    text = story["full_text"] or ""

    try:
        t1, t2 = generate_tweet_thread(title, text, client)
    except Exception as e:
        print(f"  Warning: Claude API failed ({e}), falling back to title only")
        t1, t2 = title, ""

    tweet1 = twitter_truncate(f"{t1}\n\n{HASHTAGS}", 280)
    tweet2 = twitter_truncate(f"{t2}\n\n{HASHTAGS}", 280) if t2 else ""
    return tweet1, tweet2


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Check .env or environment variables.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    init_db()
    conn = get_db()
    stories = get_top_stories(conn)
    conn.close()

    if not stories:
        print("No stories found. Run ingest.py and process.py first.")
        return

    threads = []
    for i, story in enumerate(stories, 1):
        print(f"Generating thread {i}/5: {story['title'][:60]}...")
        threads.append(format_thread(story, client))

    # Write to out/YYYY-MM-DD/
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path(__file__).resolve().parent.parent / "out" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, (t1, t2) in enumerate(threads, 1):
        (out_dir / f"tweet_{i}_1.txt").write_text(t1, encoding="utf-8")
        if t2:
            (out_dir / f"tweet_{i}_2.txt").write_text(t2, encoding="utf-8")

    print(f"\nWrote {len(threads)} threads to {out_dir}/\n")
    for i, (t1, t2) in enumerate(threads, 1):
        print(f"--- Story {i} ---")
        print(f"  Tweet 1 ({twitter_length(t1)} chars): {t1}")
        if t2:
            print(f"  Tweet 2 ({twitter_length(t2)} chars): {t2}")
        print()


if __name__ == "__main__":
    main()
