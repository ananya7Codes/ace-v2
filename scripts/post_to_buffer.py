#!/usr/bin/env python3
"""Post this week's generated tweets to X via Buffer.

Requires env vars:
  BUFFER_API_KEY       — Buffer access token
  BUFFER_X_PROFILE_ID — Buffer profile ID for your X account

Connect your X account in Buffer first (buffer.com → Channels).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

API = "https://api.bufferapp.com/1"


def get_latest_out_dir() -> Path:
    out_root = Path(__file__).resolve().parent.parent / "out"
    dirs = sorted([p for p in out_root.iterdir() if p.is_dir()])
    if not dirs:
        print("No output directories found. Run tweet.py first.")
        sys.exit(1)
    return dirs[-1]


def post_to_buffer(profile_id: str, access_token: str, text: str) -> tuple[int, str]:
    r = requests.post(
        f"{API}/updates/create.json",
        data={
            "access_token": access_token,
            "profile_ids[]": profile_id,
            "text": text,
            "now": "true",
        },
        timeout=15,
    )
    return r.status_code, r.text


def main():
    access_token = os.environ.get("BUFFER_API_KEY")
    profile_id = os.environ.get("BUFFER_X_PROFILE_ID")

    if not access_token:
        print("ERROR: BUFFER_API_KEY not set.")
        sys.exit(1)
    if not profile_id:
        print("ERROR: BUFFER_X_PROFILE_ID not set.")
        sys.exit(1)

    out_dir = get_latest_out_dir()
    print(f"Posting tweets from {out_dir.name}/\n")

    # Collect tweet_N_1.txt and tweet_N_2.txt in order
    tweet_files = sorted(out_dir.glob("tweet_*_*.txt"))
    if not tweet_files:
        print("No tweet files found. Run tweet.py first.")
        sys.exit(1)

    success = 0
    for tweet_file in tweet_files:
        text = tweet_file.read_text(encoding="utf-8").strip()
        if not text:
            continue

        print(f"Posting {tweet_file.name}...")
        status, body = post_to_buffer(profile_id, access_token, text)

        if status == 200:
            print(f"  OK\n")
            success += 1
        else:
            print(f"  FAILED ({status}): {body}\n")

    print(f"Done: {success}/{len(tweet_files)} tweets posted.")


if __name__ == "__main__":
    main()
