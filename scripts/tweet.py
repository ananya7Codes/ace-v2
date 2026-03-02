"""Pick top 5 stories and tweet them via X API v2."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from requests_oauthlib import OAuth1Session

from lib.db import get_db, init_db
from lib.settings import settings
from lib.twitter import twitter_truncate

TWEET_URL = "https://api.twitter.com/2/tweets"
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

    # Build tweet: title + summary + hashtags
    if summary:
        tweet = f"{title}\n\n{summary}\n\n{HASHTAGS}"
    else:
        tweet = f"{title}\n\n{HASHTAGS}"

    return twitter_truncate(tweet, 280)


def post_tweet(oauth: OAuth1Session, text: str) -> dict:
    resp = oauth.post(TWEET_URL, json={"text": text})
    if resp.status_code == 201:
        data = resp.json()
        tweet_id = data["data"]["id"]
        print(f"  Posted tweet {tweet_id}")
        return data
    else:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Tweet top 5 stories")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print tweets without posting"
    )
    args = parser.parse_args()

    init_db()
    conn = get_db()

    stories = get_top_stories(conn)
    conn.close()

    if not stories:
        print("No stories found. Run ingest.py and process.py first.")
        return

    tweets = [format_tweet(s) for s in stories]

    if args.dry_run:
        print(f"=== DRY RUN: {len(tweets)} tweets ===\n")
        for i, tweet in enumerate(tweets, 1):
            from lib.twitter import twitter_length

            length = twitter_length(tweet)
            print(f"--- Tweet {i} ({length} chars) ---")
            print(tweet)
            print()
        return

    # Validate credentials
    if not all(
        [
            settings.X_API_KEY,
            settings.X_API_SECRET,
            settings.X_ACCESS_TOKEN,
            settings.X_ACCESS_TOKEN_SECRET,
        ]
    ):
        print("ERROR: X API credentials not set. Check .env or environment variables.")
        sys.exit(1)

    oauth = OAuth1Session(
        settings.X_API_KEY,
        client_secret=settings.X_API_SECRET,
        resource_owner_key=settings.X_ACCESS_TOKEN,
        resource_owner_secret=settings.X_ACCESS_TOKEN_SECRET,
    )

    print(f"Posting {len(tweets)} tweets...\n")
    for i, tweet in enumerate(tweets, 1):
        print(f"--- Tweet {i} ---")
        print(tweet)
        post_tweet(oauth, tweet)
        print()

    print("Done!")


if __name__ == "__main__":
    main()
