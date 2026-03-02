"""Deduplicate, cluster, score, and promote stories from raw_items."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

from lib.db import get_db, init_db

PRACTICAL_PATTERN = re.compile(
    r"how to|launch|update|feature|workflow|template", re.IGNORECASE
)


def load_recent_items(conn, days: int = 10) -> List[dict]:
    """Load raw_items from the last N days."""
    rows = conn.execute(
        """SELECT ri.id, ri.url, ri.title, ri.text, ri.published_at, ri.meta_json,
                  s.weight
           FROM raw_items ri
           JOIN sources s ON ri.source_id = s.id
           WHERE ri.fetched_at >= datetime('now', ?)
           ORDER BY ri.published_at DESC""",
        (f"-{days} days",),
    ).fetchall()
    return [dict(r) for r in rows]


def dedupe_items(items: List[dict], threshold: float = 92.0) -> List[dict]:
    """Remove near-duplicate items using fuzzy title matching."""
    if not items:
        return []

    keep = []
    seen_titles = []

    for item in items:
        title = item["title"] or ""
        is_dupe = False
        for seen in seen_titles:
            if fuzz.token_set_ratio(title, seen) >= threshold:
                is_dupe = True
                break
        if not is_dupe:
            keep.append(item)
            seen_titles.append(title)

    print(f"  Deduped: {len(items)} → {len(keep)} items")
    return keep


def compute_scores(items: List[dict]) -> List[dict]:
    """Compute composite score for each item."""
    now = datetime.now(timezone.utc)

    for item in items:
        # Source weight (0-1.2 range)
        source_weight = item.get("weight", 1.0)

        # Recency: 1.0 if today, 0.0 if 7+ days old
        recency = 0.5  # default if no date
        if item["published_at"]:
            try:
                pub = datetime.fromisoformat(item["published_at"])
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                days_old = (now - pub).total_seconds() / 86400
                recency = max(0.0, 1.0 - days_old / 7.0)
            except (ValueError, TypeError):
                pass

        # Practical: 1.0 if practical keywords found, 0.6 otherwise
        combined_text = f"{item['title'] or ''} {item['text'] or ''}"
        practical = 1.0 if PRACTICAL_PATTERN.search(combined_text) else 0.6

        item["score"] = 25 * source_weight + 15 * recency + 20 * practical
    return items


def cluster_items(items: List[dict]) -> List[dict]:
    """Cluster items by embedding similarity, return best item per cluster."""
    if len(items) <= 5:
        print(f"  Only {len(items)} items, skipping clustering")
        return items

    print("  Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [f"{item['title'] or ''} {(item['text'] or '')[:200]}" for item in items]
    print(f"  Embedding {len(texts)} items...")
    embeddings = model.encode(texts, show_progress_bar=False)

    # Cluster with distance threshold
    n_items = len(items)
    if n_items < 2:
        for item in items:
            item["cluster_label"] = 0
        return items

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.35,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(embeddings)

    # Assign cluster labels
    for item, label in zip(items, labels):
        item["cluster_label"] = int(label)

    # Pick highest-scored item per cluster
    clusters: Dict[int, List[dict]] = {}
    for item in items:
        clusters.setdefault(item["cluster_label"], []).append(item)

    representatives = []
    for label, members in clusters.items():
        best = max(members, key=lambda x: x["score"])
        representatives.append(best)

    print(f"  Clustered into {len(representatives)} stories from {n_items} items")
    return representatives


def save_stories(conn, stories: List[dict]) -> None:
    """Save stories to the stories table."""
    now = datetime.now(timezone.utc).isoformat()

    # Clear old stories
    conn.execute("DELETE FROM stories")

    for story in stories:
        # Build a summary from the text
        text = story.get("text", "") or ""
        summary = text[:200].rsplit(" ", 1)[0] if len(text) > 200 else text

        conn.execute(
            """INSERT INTO stories (cluster_label, score, title, summary, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                story.get("cluster_label", 0),
                story["score"],
                story["title"],
                summary,
                now,
            ),
        )
    conn.commit()
    print(f"  Saved {len(stories)} stories")


def main():
    init_db()
    conn = get_db()

    print("Loading recent items...")
    items = load_recent_items(conn)
    print(f"  Found {len(items)} raw items")

    if not items:
        print("No items to process. Run ingest.py first.")
        conn.close()
        return

    print("Deduplicating...")
    items = dedupe_items(items)

    print("Scoring...")
    items = compute_scores(items)

    print("Clustering...")
    stories = cluster_items(items)

    # Sort by score descending
    stories.sort(key=lambda x: x["score"], reverse=True)

    print("Saving stories...")
    save_stories(conn, stories)

    conn.close()

    print("\nTop 5 stories:")
    for i, s in enumerate(stories[:5], 1):
        print(f"  {i}. [{s['score']:.1f}] {s['title']}")


if __name__ == "__main__":
    main()
