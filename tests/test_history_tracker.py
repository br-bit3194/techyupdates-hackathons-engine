"""
tests/test_history_tracker.py
Unit tests for persistent cross-run history tracker.
"""

import os
import json
import pytest
import tempfile
from pathlib import Path
from services.history_tracker import HistoryTracker, _normalize_title, _normalize_url
from services.ai_extractor import HackathonRecord


def test_normalize_title():
    assert _normalize_title("Google AI Hackathon 2026!") == "google ai hackathon 2026"
    assert _normalize_title("   Devpost :   Hack   Global   ") == "devpost hack global"


def test_normalize_url():
    url1 = "https://example.devpost.com/hackathons?utm_source=twitter&ref=abc"
    url2 = "https://example.devpost.com/hackathons/"
    assert _normalize_url(url1) == "https://example.devpost.com/hackathons"
    assert _normalize_url(url2) == "https://example.devpost.com/hackathons"


def test_history_tracker_deduplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        hist_file = Path(tmpdir) / "sent_history.json"
        tracker = HistoryTracker(file_path=hist_file, retention_days=30)

        # Initially empty
        assert tracker.total_records() == 0
        assert not tracker.is_duplicate("Devpost", "Google AI Hackathon", "https://google-ai.devpost.com")

        # Record a hackathon
        tracker.record_processed([
            {
                "platform": "Devpost",
                "title": "Google AI Hackathon",
                "apply_url": "https://google-ai.devpost.com?utm_source=hackathons",
                "deadline": "2026-10-15T00:00:00Z",
            }
        ])

        assert tracker.total_records() == 1

        # Check duplicate by title with different case/punctuation
        assert tracker.is_duplicate("Devpost", "google ai hackathon!", "")
        # Check duplicate by exact title
        assert tracker.is_duplicate("Devpost", "Google AI Hackathon", "")
        # Check duplicate by canonical URL
        assert tracker.is_duplicate("Devpost", "Different Title", "https://google-ai.devpost.com")

        # Check non-duplicate
        assert not tracker.is_duplicate("Unstop", "TCS CodeVita 2026", "https://unstop.com/tcs")


def test_history_tracker_persistence_across_instances():
    with tempfile.TemporaryDirectory() as tmpdir:
        hist_file = Path(tmpdir) / "sent_history.json"

        # Instance 1: Run on Day 1
        tracker1 = HistoryTracker(file_path=hist_file, retention_days=30)
        tracker1.record_processed([
            HackathonRecord(
                platform="Superteam",
                title="Superteam Solana Hackathon",
                category="Web3 & Open Source Hackathons",
                theme="DeFi & Infrastructure",
                mode="Online",
                location="Global (Online)",
                prize_pool="$50,000 USDC",
                posted_date="24 Sep 2026",
                registration_deadline="15 Oct 2026",
                event_dates="15 Oct - 30 Oct 2026",
                eligibility="Open to all developers",
                why_participate="Win from $50k prize pool and direct grant opportunities",
                apply_url="https://earn.superteam.fun/listings/hackathons/solana",
            )
        ])
        assert tracker1.total_records() == 1

        # Instance 2: Run on Day 2 (Tomorrow)
        tracker2 = HistoryTracker(file_path=hist_file, retention_days=30)
        assert tracker2.total_records() == 1

        # Tomorrow it must detect the previous day's hackathon as duplicate
        assert tracker2.is_duplicate(
            "Superteam",
            "Superteam Solana Hackathon",
            "https://earn.superteam.fun/listings/hackathons/solana?ref=telegram"
        )
