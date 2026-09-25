"""Collector for Kaggle Competitions and DoraHacks Open Source Grants (Active & Direct Links Only)."""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import KAGGLE_CONFIG, DORAHACKS_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import (
    is_registration_deadline_active,
    is_direct_hackathon_url,
    parse_date_heuristic,
)

logger = logging.getLogger("techyupdates.collectors.kaggle_dorahacks")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_kaggle_competitions(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch recently published and active prize competitions from Kaggle."""
    kaggle_competitions: List[Dict[str, Any]] = []
    seen_urls = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/xml, text/xml, application/rss+xml, */*",
    }
    now_utc = datetime.now(timezone.utc)

    try:
        resp = await client.get(KAGGLE_CONFIG["rss_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            items = soup.find_all("item")
            for item in items:
                title_elem = item.find("title")
                title = title_elem.get_text(strip=True) if title_elem else None
                link_elem = item.find("link")
                link = link_elem.get_text(strip=True) if link_elem else ""
                desc_elem = item.find("description")
                desc = desc_elem.get_text(strip=True) if desc_elem else "Machine Learning Competition"
                pub_date_elem = item.find("pubDate")
                pub_date_raw = pub_date_elem.get_text(strip=True) if pub_date_elem else ""

                if not title or not link or link in seen_urls:
                    continue

                # Ensure exact competition URL (not root or generic)
                if not is_direct_hackathon_url(link):
                    continue

                # 1. Reject past obsolete years in title or link (e.g. 2024, 2023, 2022)
                if re.search(r"\b201[0-9]\b|\b202[0-5]\b", f"{title} {link}"):
                    continue

                # 2. Check publication date - must be recent / 2026
                published_dt = parse_date_heuristic(pub_date_raw)
                if published_dt:
                    if published_dt.year < 2026:
                        continue  # Skip competitions from 2024/2025
                    pub_date_str = published_dt.strftime("%d %b %Y")
                else:
                    pub_date_str = "Past 24 Hours"

                # 3. Check deadline tags if present
                deadline_elem = item.find("kaggle:deadline") or item.find("deadline") or item.find("expiryDate")
                deadline_raw = deadline_elem.get_text(strip=True) if deadline_elem else ""
                if deadline_raw:
                    deadline_dt = parse_date_heuristic(deadline_raw)
                    if deadline_dt and deadline_dt.date() < now_utc.date():
                        continue  # Skip ended competitions
                    deadline_str = deadline_dt.strftime("%d %b %Y") if deadline_dt else deadline_raw[:10]
                else:
                    deadline_str = "Active Competition Submissions"

                seen_urls.add(link)
                kaggle_competitions.append({
                    "platform": "Kaggle",
                    "title": title,
                    "theme": "Machine Learning, LLMs & AI Modeling",
                    "mode": "Online",
                    "location": "Global (Online)",
                    "prize_pool": "Cash Awards, Points & Tier Medals",
                    "posted_date": pub_date_str,
                    "registration_deadline": deadline_str,
                    "event_dates": f"Submissions Open",
                    "eligibility": "Data Scientists, ML Researchers & Developers",
                    "apply_url": link,
                    "description": desc[:250],
                })
    except Exception as exc:
        logger.debug("Failed fetching Kaggle RSS: %s", exc)

    logger.info("Kaggle Collector ingested %d active competitions", len(kaggle_competitions))
    return kaggle_competitions


async def fetch_dorahacks_bounties(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active hackathons and developer grants from DoraHacks with exact event URLs."""
    dorahacks_events: List[Dict[str, Any]] = []
    seen_urls = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://dorahacks.io/hackathon",
    }

    try:
        resp = await client.get(DORAHACKS_CONFIG["api_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("hackathons", []) or data.get("data", []) or data.get("items", []) or (data if isinstance(data, list) else [])
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = (item.get("name") or item.get("title") or "").strip()
                    if not title:
                        continue

                    # Filter out old years
                    if re.search(r"\b201[0-9]\b|\b202[0-5]\b", title):
                        continue

                    slug = (item.get("slug") or item.get("alias") or item.get("name_alias") or item.get("id") or "").strip()
                    if not slug or slug in ["hackathons", "hackathon", "bounties"]:
                        continue

                    apply_url = f"https://dorahacks.io/hackathon/{slug}"
                    if not is_direct_hackathon_url(apply_url) or apply_url in seen_urls:
                        continue

                    status = str(item.get("status", "")).lower()
                    if status in ["ended", "closed", "past", "concluded"]:
                        continue

                    prize = item.get("reward") or item.get("prize_pool") or item.get("reward_str") or "Community Grants & Bounties"
                    posted_raw = item.get("create_time") or item.get("start_time")
                    posted_str = str(posted_raw)[:10] if posted_raw else "Past 24 Hours"

                    seen_urls.add(apply_url)
                    dorahacks_events.append({
                        "platform": "DoraHacks",
                        "title": title,
                        "theme": "Web3, Open Source & Public Goods",
                        "mode": "Online",
                        "location": "Global (Online)",
                        "prize_pool": str(prize),
                        "posted_date": posted_str,
                        "registration_deadline": "Open Registration",
                        "event_dates": "Ongoing Bounties",
                        "eligibility": "Open Source & Web3 Developers",
                        "apply_url": apply_url,
                        "description": item.get("summary") or f"Open-source developer hackathon and grant on DoraHacks: {title}.",
                    })
    except Exception as exc:
        logger.debug("Failed fetching DoraHacks events: %s", exc)

    logger.info("DoraHacks Collector ingested %d bounties", len(dorahacks_events))
    return dorahacks_events


async def fetch_kaggle_dorahacks_challenges(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Combined collector for Kaggle and DoraHacks."""
    kaggle = await fetch_kaggle_competitions(client)
    dorahacks = await fetch_dorahacks_bounties(client)
    return kaggle + dorahacks
