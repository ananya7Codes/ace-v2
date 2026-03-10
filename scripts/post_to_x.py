#!/usr/bin/env python3
"""Post this week's tweet threads directly to X via API v2.

Each story is posted as a proper 2-tweet thread:
  tweet_N_1.txt  → posted first
  tweet_N_2.txt  → posted as a reply to tweet_N_1

Requires env vars:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import tweepy


def get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def get_latest_out_dir() -> Path:
    out_root = Path(__file__).resolve().parent.parent / "out"
    dirs = sorted([p for p in out_root.iterdir() if p.is_dir()])
    if not dirs:
        print("No output directories found. Run tweet.py first.")
        sys.exit(1)
    return dirs[-1]


def post_thread(client: tweepy.Client, t1: str, t2: str, label: str):
    """Post t1, then t2 as a reply to form a thread."""
    resp = client.create_tweet(text=t1)
    tweet_id = resp.data["id"]
    print(f"  {label} tweet 1 posted (id={tweet_id})")

    if t2:
        time.sleep(2)  # brief pause between thread tweets
        client.create_tweet(text=t2, in_reply_to_tweet_id=tweet_id)
        print(f"  {label} tweet 2 posted as reply")


def main():
    for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        if not os.environ.get(key):
            print(f"ERROR: {key} not set.")
            sys.exit(1)

    client = get_client()
    out_dir = get_latest_out_dir()
    print(f"Posting threads from {out_dir.name}/\n")

    success = 0
    for i in range(1, 6):
        t1_file = out_dir / f"tweet_{i}_1.txt"
        t2_file = out_dir / f"tweet_{i}_2.txt"

        if not t1_file.exists():
            continue

        t1 = t1_file.read_text(encoding="utf-8").strip()
        t2 = t2_file.read_text(encoding="utf-8").strip() if t2_file.exists() else ""

        try:
            post_thread(client, t1, t2, label=f"Story {i}")
            success += 1
            time.sleep(3)  # pause between stories
        except Exception as e:
            print(f"  Story {i} FAILED: {e}")

    print(f"\nDone: {success}/5 threads posted.")


if __name__ == "__main__":
    main()
