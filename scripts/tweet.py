"""Pick top 5 stories, generate coherent tweets via Claude, write to out/YYYY-MM-DD/."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

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


def generate_tweet_text(title: str, text: str, client: anthropic.Anthropic) -> str:
    """Use Claude Haiku to write a coherent, informative tweet under 240 chars."""
    prompt = f"""Write a tweet about this AI news story.

Rules:
- Maximum 240 characters
- Tell the actual news — be specific and informative, not just the headline
- Plain English, no jargon
- No hashtags, no URLs
- Return only the tweet text, nothing else

Title: {title}
Full story: {text[:3000]}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    tweet = response.content[0].text.strip()
    # Hard cap as safety net
    if len(tweet) > 240:
        tweet = tweet[:239] + "…"
    return tweet


def format_tweet(story: dict, client: anthropic.Anthropic) -> str:
    title = story["title"] or "Untitled"
    text = story["full_text"] or ""

    try:
        body = generate_tweet_text(title, text, client)
    except Exception as e:
        print(f"  Warning: Claude API failed ({e}), falling back to title only")
        body = title

    return twitter_truncate(f"{body}\n\n{HASHTAGS}", 280)


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

    tweets = []
    for i, story in enumerate(stories, 1):
        print(f"Generating tweet {i}/5: {story['title'][:60]}...")
        tweets.append(format_tweet(story, client))

    # Write to out/YYYY-MM-DD/
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path(__file__).resolve().parent.parent / "out" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, tweet in enumerate(tweets, 1):
        (out_dir / f"tweet_{i}.txt").write_text(tweet, encoding="utf-8")

    print(f"\nWrote {len(tweets)} tweets to {out_dir}/\n")
    for i, tweet in enumerate(tweets, 1):
        print(f"--- Tweet {i} ({twitter_length(tweet)} chars) ---")
        print(tweet)
        print()


if __name__ == "__main__":
    main()
