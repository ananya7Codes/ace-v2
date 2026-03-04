"""Fetch RSS feeds and store raw items in SQLite."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from lib.db import get_db, init_db

SCRAPE_TIMEOUT = 10       # seconds per article request
SCRAPE_DELAY   = 0.3      # seconds between requests (be polite)
MAX_TEXT_LEN   = 8000     # chars to store per article


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


def scrape_article(url: str) -> str:
    """Fetch an article URL and extract the main body text."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ACE-bot/1.0; +https://github.com/ananya7Codes/ace-v2)"}
        resp = requests.get(url, timeout=SCRAPE_TIMEOUT, headers=headers)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "figure"]):
            tag.decompose()

        # Try article → main → body, in order of specificity
        container = soup.find("article") or soup.find("main") or soup.body
        if not container:
            return ""

        paragraphs = container.find_all("p")
        text = " ".join(p.get_text(separator=" ", strip=True) for p in paragraphs)
        return text[:MAX_TEXT_LEN]
    except Exception:
        return ""


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

        # Extract text from RSS content/summary first
        text = ""
        if hasattr(entry, "content") and entry.content:
            text = strip_html(entry.content[0].get("value", ""))
        elif hasattr(entry, "summary"):
            text = strip_html(entry.summary)

        # If RSS gave us nothing useful, scrape the article URL
        if len(text.strip()) < 100 and link:
            scraped = scrape_article(link)
            if scraped:
                text = scraped
            time.sleep(SCRAPE_DELAY)

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
