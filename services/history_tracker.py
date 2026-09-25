"""
services/history_tracker.py
Persistent cross-run deduplication store to prevent sending duplicate
hackathon opportunities across consecutive daily runs.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("hackathons_engine.history")

# Default history storage file located in project data/ directory
DEFAULT_HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "sent_history.json"
DEFAULT_RETENTION_DAYS = 30


def _normalize_title(title: str) -> str:
    """Normalize title for cross-run matching (lowercase, alphanumeric)."""
    cleaned = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(cleaned.split())


def _normalize_url(url: str) -> str:
    """Strip query parameters and trailing slashes for canonical URL comparison."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        # Strip query parameters (UTM tags, tracking tokens, etc.)
        cleaned = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
        return cleaned
    except Exception:
        return url.strip().lower().rstrip("/")


class HistoryTracker:
    """Manages persistent history of discovered & notified hackathons across runs."""

    def __init__(self, file_path: Optional[Union[str, Path]] = None, retention_days: int = DEFAULT_RETENTION_DAYS):
        self.file_path = Path(file_path) if file_path else DEFAULT_HISTORY_FILE
        self.retention_days = retention_days
        self._history: Dict[str, Dict[str, Any]] = {}
        self._title_hashes: Set[str] = set()
        self._url_hashes: Set[str] = set()
        self._load_history()

    def _load_history(self) -> None:
        """Load history from persistent JSON file."""
        self._history = {}
        self._title_hashes = set()
        self._url_hashes = set()

        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
                valid_entries = {}

                for key, entry in data.items():
                    # Parse recorded timestamp
                    first_seen_str = entry.get("first_seen")
                    if first_seen_str:
                        try:
                            first_seen_dt = datetime.fromisoformat(first_seen_str)
                            if first_seen_dt.tzinfo is None:
                                first_seen_dt = first_seen_dt.replace(tzinfo=timezone.utc)
                            if first_seen_dt < cutoff:
                                continue  # Prune expired entries
                        except Exception:
                            pass

                    valid_entries[key] = entry
                    
                    # Index normalized title and URL
                    norm_title = entry.get("norm_title")
                    if norm_title:
                        self._title_hashes.add(norm_title)

                    norm_url = entry.get("norm_url")
                    if norm_url:
                        self._url_hashes.add(norm_url)

                self._history = valid_entries
                logger.info("Loaded %d historical hackathon records from %s", len(self._history), self.file_path.name)
        except Exception as exc:
            logger.warning("Failed to load history from %s (will start fresh): %s", self.file_path, exc)
            self._history = {}

    def is_duplicate(self, platform: str, title: str, apply_url: str = "") -> bool:
        """
        Check if a hackathon has been processed/sent in a prior run.
        Checks against:
        1. Exact title + platform signature
        2. Normalized title match
        3. Canonical apply URL match
        """
        if not title:
            return False

        norm_title = _normalize_title(title)
        if norm_title and norm_title in self._title_hashes:
            return True

        if apply_url:
            norm_url = _normalize_url(apply_url)
            if norm_url and norm_url in self._url_hashes:
                return True

        return False

    def record_processed(self, items: List[Any]) -> int:
        """
        Record newly processed hackathons into the persistent history store.
        Accepts dicts or HackathonRecord objects.
        """
        if not items:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        added_count = 0

        for item in items:
            if hasattr(item, "title"):
                # Pydantic or object model
                title = getattr(item, "title", "")
                platform = getattr(item, "platform", "")
                apply_url = getattr(item, "apply_url", "")
                deadline = getattr(item, "deadline", "")
            elif isinstance(item, dict):
                title = item.get("title", "")
                platform = item.get("platform", "")
                apply_url = item.get("apply_url", "")
                deadline = item.get("deadline", "")
            else:
                continue

            if not title:
                continue

            norm_title = _normalize_title(title)
            norm_url = _normalize_url(apply_url)
            entry_key = f"{platform.lower().strip()}:{norm_title}"

            self._history[entry_key] = {
                "title": title,
                "norm_title": norm_title,
                "platform": platform,
                "apply_url": apply_url,
                "norm_url": norm_url,
                "deadline": deadline,
                "first_seen": now_iso,
            }
            if norm_title:
                self._title_hashes.add(norm_title)
            if norm_url:
                self._url_hashes.add(norm_url)
            added_count += 1

        self._save_history()
        return added_count

    def _save_history(self) -> None:
        """Persist history entries to disk."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
            logger.info("Persisted %d total hackathon history records to %s", len(self._history), self.file_path.name)
        except Exception as exc:
            logger.error("Failed to save history file %s: %s", self.file_path, exc)

    def total_records(self) -> int:
        """Return total active records tracked in history."""
        return len(self._history)
