"""Liveness, Verification, and URL Directness Engine for Hackathons."""

import hashlib
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse
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
    "contest has concluded",
    "applications closed",
]

EXPIRED_PATTERNS = [
    r"\bended\b",
    r"\bclosed\b",
    r"\bexpired\b",
    r"\bconcluded\b",
    r"\bdeadline passed\b",
    r"\bpassed\b",
]

OBSOLETE_YEARS = [r"\b201[0-9]\b", r"\b202[0-4]\b"]

# Generic filter, directory, and search page endpoints that are NOT direct hackathon pages
GENERIC_FILTER_PATTERNS = [
    r"^https?://(?:www\.)?devpost\.com/hackathons(?:\?.*)?$",
    r"^https?://(?:www\.)?devpost\.com/?$",
    r"^https?://(?:www\.)?devpost\.com/software/?$",
    r"^https?://(?:www\.)?unstop\.com/hackathons/?$",
    r"^https?://(?:www\.)?unstop\.com/competitions/?$",
    r"^https?://(?:www\.)?unstop\.com/opportunities/?$",
    r"^https?://(?:www\.)?unstop\.com/?$",
    r"^https?://(?:www\.)?devfolio\.co/hackathons/?$",
    r"^https?://(?:www\.)?devfolio\.co/?$",
    r"^https?://(?:www\.)?mlh\.io/seasons(?:/.*)?$",
    r"^https?://(?:www\.)?mlh\.io/?$",
    r"^https?://(?:www\.)?hack2skill\.com/hackathons(?:-listing)?/?$",
    r"^https?://(?:www\.)?hack2skill\.com/?$",
    r"^https?://(?:www\.)?hack2skill\.com/events/?$",
    r"^https?://(?:www\.)?kaggle\.com/competitions/?$",
    r"^https?://(?:www\.)?kaggle\.com/?$",
    r"^https?://(?:www\.)?dorahacks\.io/hackathon/?$",
    r"^https?://(?:www\.)?dorahacks\.io/?$",
    r"^https?://(?:www\.)?hackerearth\.com/challenges/?$",
    r"^https?://(?:www\.)?earn\.superteam\.fun/?$",
]


def is_direct_hackathon_url(url: str) -> bool:
    """Verify that the URL points to a specific hackathon, and NOT a generic search/filter listing."""
    if not url or not isinstance(url, str):
        return False
    clean_url = url.strip().split("#")[0]

    # Must start with http/https
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return False

    # Check against generic filter patterns
    for pat in GENERIC_FILTER_PATTERNS:
        if re.match(pat, clean_url, re.IGNORECASE):
            logger.debug("Filtered out generic directory URL: %s", clean_url)
            return False

    try:
        parsed = urlparse(clean_url)
        if not (parsed.netloc and "." in parsed.netloc):
            return False

        # Devpost: Must be a subdomain (e.g., gemini.devpost.com) or a specific path
        if "devpost.com" in parsed.netloc:
            parts = parsed.netloc.split(".")
            if len(parts) >= 3 and parts[0] not in ["www", "help", "info"]:
                return True  # Valid subdomain like aws.devpost.com
            if parsed.path.rstrip("/") in ["", "/hackathons", "/software", "/rules", "/about"]:
                return False

        return True
    except Exception:
        return False


# Alias for backwards compatibility
is_valid_apply_url = is_direct_hackathon_url


def normalize_string_for_hash(text: str) -> str:
    """Normalize text by stripping punctuation, extra spaces, and common stop words."""
    if not text:
        return ""
    cleaned = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\b(hackathon|challenge|buildathon|2025|2026|online|the|a|an)\b", "", cleaned)
    return " ".join(cleaned.split())


def generate_dedup_hash(platform: str, title: str) -> str:
    """Generate MD5 signature for cross-platform deduplication."""
    norm_title = normalize_string_for_hash(title)
    norm_plat = platform.strip().lower().split("(")[0].strip()
    cleaned = f"{norm_plat}:{norm_title}"
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()


def is_scam_or_blacklisted(item: Dict[str, Any]) -> bool:
    """Detect scammy, fraudulent, or blacklisted competitions."""
    text_corpus = f"{item.get('title', '')} {item.get('description', '')} {item.get('prize_pool', '')}".lower()
    for kw in SCAM_BLACKLIST_KEYWORDS:
        if kw in text_corpus:
            logger.debug("Filtered scam/blacklisted hackathon: '%s' matching '%s'", item.get("title"), kw)
            return True
    return False


def parse_date_heuristic(date_str: str) -> Optional[datetime]:
    """Parse various date representations to a UTC datetime object."""
    if not date_str or not isinstance(date_str, str):
        return None

    clean_str = date_str.strip().replace("Z", "+00:00")
    clean_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", clean_str)

    try:
        return datetime.fromisoformat(clean_str).astimezone(timezone.utc)
    except Exception:
        pass

    formats_to_try = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%b %d %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%Y/%m/%d",
    ]

    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(clean_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    date_part = clean_str[:10]
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_part, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def is_registration_deadline_active(date_input: Any, title_context: str = "") -> bool:
    """Strictly verify that registration is currently open and deadline has NOT passed."""
    deadline_str = str(date_input.get("registration_deadline", "") if isinstance(date_input, dict) else date_input).strip().lower()
    title_str = str(date_input.get("title", "") if isinstance(date_input, dict) else title_context).strip().lower()
    desc_str = str(date_input.get("description", "") if isinstance(date_input, dict) else "").strip().lower()
    corpus = f"{deadline_str} {title_str} {desc_str}"

    # 1. Reject obsolete historical years anywhere in the event metadata
    for year_pat in OBSOLETE_YEARS:
        if re.search(year_pat, corpus):
            logger.debug("Filtered expired year in '%s' / '%s'", title_str, deadline_str)
            return False

    # 2. Reject explicit closure / expired / past markers
    for pat in EXPIRED_PATTERNS:
        if re.search(pat, deadline_str) or re.search(pat, corpus):
            if any(m in corpus for m in ["registration closed", "submissions closed", "event ended", "contest concluded", "applications closed", "deadline passed"]):
                logger.debug("Filtered explicit closure in '%s'", title_str)
                return False

    # 3. Absolute Date Precedence: If a date is found, it MUST be today or in the future
    parsed_dt = parse_date_heuristic(deadline_str)
    if not parsed_dt:
        # Also try to extract a date from event_dates if available
        if isinstance(date_input, dict) and date_input.get("event_dates"):
            parsed_dt = parse_date_heuristic(str(date_input["event_dates"]))

    if parsed_dt:
        now_utc = datetime.now(timezone.utc)
        if parsed_dt.date() < now_utc.date():
            logger.debug("Filtered past deadline %s (Today: %s) for '%s'",
                         parsed_dt.date().isoformat(), now_utc.date().isoformat(), title_str)
            return False
        return True

    # 4. Strict active positive keywords required if no absolute date is present
    strict_active_keywords = [
        "open", "rolling", "ongoing", "active", "upcoming", "live",
        "accepting", "days left", "hours left", "weeks left",
        "season", "bounty", "grand finale", "championship", "sprint"
    ]
    if any(k in deadline_str for k in strict_active_keywords):
        return True

    # If ambiguous or unverified, reject to maintain high quality
    logger.debug("Filtered ambiguous deadline '%s' for '%s'", deadline_str, title_str)
    return False


def is_recent_or_past_24h_posted(item: Dict[str, Any], max_age_days: int = 3) -> bool:
    """Verify that the hackathon was posted/launched recently (within the daily 24h-48h window)."""
    posted_raw = str(item.get("posted_date") or item.get("created_at") or item.get("pubDate") or "").strip()
    if not posted_raw:
        return True  # If not explicitly stamped, trust collector's sort=recent query

    posted_lower = posted_raw.lower()
    recent_phrases = ["past 24 hours", "today", "yesterday", "hours ago", "1 day ago", "2 days ago", "just now", "active 2026", "active season"]
    if any(p in posted_lower for p in recent_phrases):
        return True

    # Parse absolute posted date
    parsed_posted = parse_date_heuristic(posted_raw)
    if parsed_posted:
        now_utc = datetime.now(timezone.utc)
        age_days = (now_utc.date() - parsed_posted.date()).days
        # Reject if published more than max_age_days in the past
        if age_days > max_age_days:
            logger.debug("Filtered out old post '%s': published %d days ago (%s)",
                         item.get("title"), age_days, parsed_posted.date().isoformat())
            return False
        if age_days < 0:
            return True  # Future/scheduled launch is valid
        return True

    return True


async def verify_single_hackathon_liveness(client: httpx.AsyncClient, hackathon: Dict[str, Any]) -> bool:
    """Verify if a single hackathon link is direct, posted recently, and actively accepting registrations."""
    # 1. Direct URL check (strictly filter out directory/filter pages)
    url = hackathon.get("apply_url", "")
    if not is_direct_hackathon_url(url):
        logger.debug("Filtered non-direct URL: %s", url)
        return False

    # 2. Strict Past 24h / Recent check
    if not is_recent_or_past_24h_posted(hackathon):
        return False

    # 3. Deadline status check
    if not is_registration_deadline_active(hackathon):
        return False

    # 4. Active HTTP Liveness & 404 Verification Probe
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = await client.get(url, headers=headers, timeout=6.0, follow_redirects=True)
        # Reject 404 Not Found, 410 Gone, 500, 502, 503
        if resp.status_code >= 400:
            logger.debug("Filtered broken URL (HTTP %d): %s", resp.status_code, url)
            return False

        # Reject if redirected to a generic homepage, directory, or 404 path
        final_url = str(resp.url).lower().split("?")[0].rstrip("/")
        if not is_direct_hackathon_url(final_url) or final_url.endswith("/404") or final_url.endswith("/not-found"):
            logger.debug("Filtered redirected generic/404 URL '%s' -> '%s'", url, final_url)
            return False

        # Check body for soft 404s or explicit event closure markers
        body_lower = resp.text.lower()[:8000]  # inspect first 8KB
        soft_404_markers = [
            "404 - page not found",
            "page not found",
            "this page could not be found",
            "the requested url was not found",
            "challenge not found",
            "event does not exist",
            "this initiative isn’t live yet",
            "this initiative isn't live yet",
            "initiative may be unpublished",
            "temporarily unavailable",
            "initiative isn't live",
            "initiative is not live",
        ]
        if any(m in body_lower for m in soft_404_markers):
            logger.debug("Filtered soft 404 / unpublished page on '%s'", url)
            return False

        for marker in CLOSURE_MARKERS:
            if marker in body_lower:
                logger.debug("Filtered closed registration marker on '%s'", url)
                return False

        return True
    except httpx.TimeoutException:
        logger.debug("HTTP probe timed out for '%s', permitting trusted domain", url)
        return True  # Preserve if server is slow but domain is verified
    except Exception as exc:
        logger.debug("HTTP probe error on '%s': %s", url, exc)
        return False


async def verify_hackathons_liveness(hackathons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Concurrently check liveness, direct URL validity, and registration status for hackathons."""
    if not hackathons:
        return []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        tasks = [verify_single_hackathon_liveness(client, h) for h in hackathons]
        results: Tuple[bool, ...] = await asyncio.gather(*tasks, return_exceptions=True)

    active_hackathons: List[Dict[str, Any]] = []
    for item, is_active in zip(hackathons, results):
        if is_active is True:
            active_hackathons.append(item)

    logger.info("Liveness check verified %d/%d direct, active hackathons", len(active_hackathons), len(hackathons))
    return active_hackathons
