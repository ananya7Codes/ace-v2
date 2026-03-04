"""Pick top 5 stories and write them as tweet files to out/YYYY-MM-DD/."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.db import get_db, init_db
from lib.twitter import twitter_length, twitter_truncate

HASHTAGS = "#AI #Tech"


def get_top_stories(conn, limit: int = 5) -> List[dict]:
    rows = conn.execute(
        "SELECT title, summary, score FROM stories ORDER BY score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def format_tweet(story: dict) -> str:
    """Format a story into a tweet."""
    title = story["title"] or "Untitled"
    summary = story["summary"] or ""

    if summary:
        tweet = f"{title}\n\n{summary}\n\n{HASHTAGS}"
    else:
        tweet = f"{title}\n\n{HASHTAGS}"

    return twitter_truncate(tweet, 280)


def main():
    init_db()
    conn = get_db()

    stories = get_top_stories(conn)
    conn.close()

    if not stories:
        print("No stories found. Run ingest.py and process.py first.")
        return

    tweets = [format_tweet(s) for s in stories]

    # Write to out/YYYY-MM-DD/
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path(__file__).resolve().parent.parent / "out" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, tweet in enumerate(tweets, 1):
        out_file = out_dir / f"tweet_{i}.txt"
        out_file.write_text(tweet, encoding="utf-8")

    print(f"Wrote {len(tweets)} tweets to {out_dir}/\n")
    for i, tweet in enumerate(tweets, 1):
        length = twitter_length(tweet)
        print(f"--- Tweet {i} ({length} chars) ---")
        print(tweet)
        print()


if __name__ == "__main__":
    main()
