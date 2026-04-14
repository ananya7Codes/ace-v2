#!/usr/bin/env python3
"""Post this week's top 5 tweets to X via Buffer API.

Reads tweet_N_1.txt from the latest out/ directory and schedules
each one to post now via Buffer. Requires your X profile connected
in Buffer.

Requires env vars:
  BUFFER_API_KEY, BUFFER_X_PROFILE_ID
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

BUFFER_API = "https://api.bufferapp.com/1"


def get_latest_out_dir() -> Path:
    out_root = Path(__file__).resolve().parent.parent / "out"
    dirs = sorted([p for p in out_root.iterdir() if p.is_dir()])
    if not dirs:
        print("No output directories found. Run tweet.py first.")
        sys.exit(1)
    return dirs[-1]


def post_to_buffer(profile_id: str, api_key: str, text: str) -> bool:
    resp = requests.post(
        f"{BUFFER_API}/updates/create.json",
        data={
            "access_token": api_key,
            "profile_ids[]": profile_id,
            "text": text,
            "now": "true",
        },
    )
    if resp.status_code == 200:
        return True
    print(f"  Buffer error {resp.status_code}: {resp.text}")
    return False


def main():
    api_key = os.environ.get("BUFFER_API_KEY")
    profile_id = os.environ.get("BUFFER_X_PROFILE_ID")

    if not api_key or not profile_id:
        print("ERROR: BUFFER_API_KEY and BUFFER_X_PROFILE_ID must be set.")
        sys.exit(1)

    out_dir = get_latest_out_dir()
    print(f"Posting tweets from {out_dir.name}/\n")

    success = 0
    for i in range(1, 6):
        tweet_file = out_dir / f"tweet_{i}_1.txt"
        if not tweet_file.exists():
            continue

        text = tweet_file.read_text(encoding="utf-8").strip()
        if post_to_buffer(profile_id, api_key, text):
            print(f"  Story {i} posted ({len(text)} chars)")
            success += 1
        else:
            print(f"  Story {i} FAILED")

        time.sleep(2)  # be polite to Buffer API

    print(f"\nDone: {success}/5 tweets posted.")


if __name__ == "__main__":
    main()
