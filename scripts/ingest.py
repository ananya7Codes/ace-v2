"""Fetch RSS feeds and store raw items in SQLite."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from lib.db import get_db, init_db


def load_sources() -> List[dict]:
    config_path = Path(__file__).resolve().parent.parent / "configs" / "sources.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)["sources"]


def upsert_sources(conn, sources: List[dict]) -> Dict[str, int]:
    """Insert or update sources and return name->id mapping."""
    name_to_id = {}
    for src in sources:
        conn.execute(
            """INSERT INTO sources (name, url, kind, weight)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                 name=excluded.name, kind=excluded.kind, weight=excluded.weight""",
            (src["name"], src["url"], src["kind"], src["weight"]),
        )
        row = conn.execute(
            "SELECT id FROM sources WHERE url = ?", (src["url"],)
        ).fetchone()
        name_to_id[src["name"]] = row["id"]
    conn.commit()
    return name_to_id


def strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def parse_date(entry) -> Optional[str]:
    for field in ("published", "updated"):
        val = getattr(entry, field, None) or entry.get(field)
        if val:
            try:
                dt = dateparser.parse(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
    return None


def fetch_feed(source: dict, source_id: int, conn) -> int:
    """Fetch one RSS feed and insert items. Returns count of new items."""
    now = datetime.now(timezone.utc).isoformat()
    feed = feedparser.parse(source["url"])
    inserted = 0

    for entry in feed.entries:
        link = getattr(entry, "link", None) or entry.get("link", "")
        if not link:
            continue

        item_id = make_id(link)
        title = getattr(entry, "title", "") or ""
        author = getattr(entry, "author", "") or ""
        published = parse_date(entry)

        # Extract text from summary/content
        text = ""
        if hasattr(entry, "content") and entry.content:
            text = strip_html(entry.content[0].get("value", ""))
        elif hasattr(entry, "summary"):
            text = strip_html(entry.summary)

        meta = json.dumps({"source_name": source["name"], "weight": source["weight"]})

        try:
            conn.execute(
                """INSERT OR IGNORE INTO raw_items
                   (id, source_id, url, title, author, published_at, text, meta_json, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, source_id, link, title, author, published, text, meta, now),
            )
            if conn.total_changes:
                inserted += 1
        except Exception as e:
            print(f"  Warning: could not insert {link}: {e}")

    return inserted


def main():
    init_db()
    conn = get_db()

    sources = load_sources()
    name_to_id = upsert_sources(conn, sources)

    total = 0
    for src in sources:
        print(f"Fetching {src['name']}... ", end="", flush=True)
        try:
            count = fetch_feed(src, name_to_id[src["name"]], conn)
            print(f"{count} new items")
            total += count
        except Exception as e:
            print(f"ERROR: {e}")

    conn.commit()
    conn.close()

    print(f"\nIngestion complete: {total} new items total")


if __name__ == "__main__":
    main()
