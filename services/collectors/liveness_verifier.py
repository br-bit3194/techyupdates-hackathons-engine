"""Liveness and Active Registration Verifier for Hackathons."""

import hashlib
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import httpx
from config.targets import SCAM_BLACKLIST_KEYWORDS, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger("techyupdates.liveness_verifier")

CLOSURE_MARKERS = [
    "registration closed",
    "registrations are closed",
    "hackathon has ended",
    "submissions closed",
    "event has ended",
    "application deadline passed",
    "no longer accepting submissions",
    "submissions have closed",
    "registration is over",
]

EXPIRED_PATTERNS = [
    r"\bended\b",
    r"\bclosed\b",
    r"\bexpired\b",
    r"\bpast\b",
    r"\bconcluded\b",
    r"\bdeadline passed\b",
]


def generate_dedup_hash(platform: str, title: str) -> str:
    """Generate MD5 signature for deduplication."""
    cleaned = f"{platform.strip().lower()}:{title.strip().lower()}"
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()


def is_scam_or_blacklisted(item: Dict[str, Any]) -> bool:
    """Detect scammy, spam, or blacklisted competitions."""
    text_corpus = f"{item.get('title', '')} {item.get('description', '')} {item.get('prize_pool', '')}".lower()
    for kw in SCAM_BLACKLIST_KEYWORDS:
        if kw in text_corpus:
            logger.debug("Filtered scam/blacklisted hackathon: '%s' matching '%s'", item.get("title"), kw)
            return True
    return False


def parse_date_heuristic(date_str: str) -> Optional[datetime]:
    """Parse common date formats to a UTC datetime object."""
    if not date_str:
        return None

    clean_str = date_str.strip().replace("Z", "+00:00")
    
    # Try ISO formats first
    try:
        return datetime.fromisoformat(clean_str).astimezone(timezone.utc)
    except Exception:
        pass

    # Try common regex formats
    formats_to_try = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y/%m/%d",
    ]
    # Extract date prefix if trailing time info is present
    date_part = clean_str[:10]
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_part, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            try:
                dt = datetime.strptime(clean_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

    return None


def is_registration_deadline_active(item: Dict[str, Any]) -> bool:
    """Verify that registration is open and deadline is in the future."""
    deadline_str = str(item.get("registration_deadline", "")).strip().lower()
    desc_str = str(item.get("description", "")).strip().lower()
    corpus = f"{deadline_str} {desc_str}"

    # 1. Check for explicit closure/past keywords
    for pat in EXPIRED_PATTERNS:
        if re.search(pat, deadline_str):
            logger.debug("Filtered hackathon '%s': deadline '%s' matches expired pattern '%s'",
                         item.get("title"), deadline_str, pat)
            return False

    # 2. Check for active/relative keywords
    if any(k in deadline_str for k in ["open", "rolling", "ongoing", "active", "upcoming", "live", "left", "today", "tomorrow", "days left"]):
        return True

    # 3. Parse absolute date if present
    parsed_dt = parse_date_heuristic(item.get("registration_deadline", ""))
    if parsed_dt:
        now_utc = datetime.now(timezone.utc)
        # Allow today's date through the end of the day
        if parsed_dt.date() < now_utc.date():
            logger.info("Filtered past hackathon '%s': deadline was %s (Today: %s)",
                        item.get("title"), parsed_dt.date().isoformat(), now_utc.date().isoformat())
            return False
        return True

    # If date format is unspecified but not explicitly marked expired, keep as open
    return True


async def verify_single_hackathon_liveness(client: httpx.AsyncClient, hackathon: Dict[str, Any]) -> bool:
    """Verify if a single hackathon link is still actively accepting registrations."""
    # 1. First verify deadline status
    if not is_registration_deadline_active(hackathon):
        return False

    url = hackathon.get("apply_url", "")
    platform = hackathon.get("platform", "")

    # Fast-path: Verified official partner endpoints bypass redundant GET requests
    if any(k in platform.lower() for k in ["devpost", "unstop", "devfolio", "mlh", "major league hacking", "kaggle", "dorahacks"]):
        return True

    if not url or not url.startswith("http"):
        return False

    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
        if resp.status_code >= 400:
            return False

        body_lower = resp.text.lower()
        for marker in CLOSURE_MARKERS:
            if marker in body_lower:
                logger.debug("Filtered closed hackathon '%s' matching marker '%s'", hackathon.get("title"), marker)
                return False

        return True
    except Exception as exc:
        logger.debug("Liveness check failed for '%s': %s", url, exc)
        return True  # Soft-fail to preserve opportunity in case of intermittent network blocks


async def verify_hackathons_liveness(hackathons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Concurrently check liveness and registration status for a list of hackathons."""
    if not hackathons:
        return []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        tasks = [verify_single_hackathon_liveness(client, h) for h in hackathons]
        results: Tuple[bool, ...] = await asyncio.gather(*tasks, return_exceptions=True)

    active_hackathons: List[Dict[str, Any]] = []
    for item, is_active in zip(hackathons, results):
        if is_active is True:
            active_hackathons.append(item)

    logger.info("Liveness check verified %d/%d active hackathons", len(active_hackathons), len(hackathons))
    return active_hackathons
