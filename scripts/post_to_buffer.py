#!/usr/bin/env python3
"""Post this week's generated tweets to X via Buffer GraphQL API.

Requires env vars:
  BUFFER_API_KEY       — Buffer personal API key (Settings → API)
  BUFFER_X_CHANNEL_ID — Buffer channel ID for your X account

Connect your X account in Buffer first (buffer.com → Channels).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API = "https://api.buffer.com/graphql"

CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post { id text }
    }
    ... on NotFoundError { message }
    ... on UnauthorizedError { message }
    ... on UnexpectedError { message }
    ... on RestProxyError { message }
    ... on LimitReachedError { message }
    ... on InvalidInputError { message }
  }
}
"""


def post_to_buffer(channel_id: str, access_token: str, text: str) -> tuple[bool, str]:
    r = requests.post(
        API,
        json={
            "query": CREATE_POST,
            "variables": {
                "input": {
                    "channelId": channel_id,
                    "text": text,
                    "schedulingType": "automatic",
                    "mode": "shareNow",
                }
            },
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = r.json()
    if r.status_code != 200:
        return False, r.text
    result = data.get("data", {}).get("createPost", {})
    if "message" in result:
        return False, result["message"]
    return True, ""


def get_latest_out_dir() -> Path:
    out_root = Path(__file__).resolve().parent.parent / "out"
    dirs = sorted([p for p in out_root.iterdir() if p.is_dir()])
    if not dirs:
        print("No output directories found. Run tweet.py first.")
        sys.exit(1)
    return dirs[-1]


def main():
    import re
    dry_run = "--dry-run" in sys.argv

    access_token = os.environ.get("BUFFER_API_KEY")
    channel_id = os.environ.get("BUFFER_X_CHANNEL_ID")

    if not dry_run:
        if not access_token:
            print("ERROR: BUFFER_API_KEY not set.")
            sys.exit(1)
        if not channel_id:
            print("ERROR: BUFFER_X_CHANNEL_ID not set.")
            sys.exit(1)

    out_dir = get_latest_out_dir()
    print(f"{'[DRY RUN] ' if dry_run else ''}Posting tweets from {out_dir.name}/\n")

    # Only use tweet_N_M.txt format (skip bare tweet_N.txt duplicates)
    tweet_files = sorted(out_dir.glob("tweet_*_*.txt"))
    if not tweet_files:
        print("No tweet files found. Run tweet.py first.")
        sys.exit(1)

    # Group by story number to know total tweets per story
    stories: dict[str, list[Path]] = {}
    for f in tweet_files:
        m = re.match(r"tweet_(\d+)_(\d+)\.txt", f.name)
        if m:
            stories.setdefault(m.group(1), []).append(f)

    success = 0
    total = 0
    for story_num, parts in sorted(stories.items()):
        parts = sorted(parts)
        total_parts = len(parts)
        for idx, tweet_file in enumerate(parts, 1):
            text = tweet_file.read_text(encoding="utf-8").strip()
            if not text:
                continue
            if total_parts > 1:
                text = f"{idx}/{total_parts} {text}"
            total += 1
            if dry_run:
                print(f"[{tweet_file.name}]\n{text}\n({len(text)} chars)\n")
                success += 1
                continue
            print(f"Posting {tweet_file.name} ({idx}/{total_parts})...")
            ok, err = post_to_buffer(channel_id, access_token, text)
            if ok:
                print(f"  OK\n")
                success += 1
            else:
                print(f"  FAILED: {err}\n")

    print(f"Done: {success}/{total} tweets {'previewed' if dry_run else 'posted'}.")


if __name__ == "__main__":
    main()
