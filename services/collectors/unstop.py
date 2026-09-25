"""Collector for Unstop Hackathons, Coding Challenges, and Hiring Contests (Active & Open)."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from config.targets import UNSTOP_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import is_registration_deadline_active

logger = logging.getLogger("techyupdates.collectors.unstop")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def format_unstop_date(date_raw: Any) -> str:
    """Format raw date string into readable DD Mon YYYY."""
    if not date_raw:
        return "Open Registration"
    date_str = str(date_raw).strip()
    try:
        clean = date_str[:10]
        dt = datetime.strptime(clean, "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return date_str[:16]


async def fetch_unstop_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active opportunities from Unstop public search endpoints."""
    hackathons: List[Dict[str, Any]] = []
    seen_urls = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://unstop.com/hackathons",
    }
    now_utc = datetime.now(timezone.utc)

    for cat in UNSTOP_CONFIG["categories"]:
        # Query recently added/open opportunities
        url = f"{UNSTOP_CONFIG['api_url']}?opportunity={cat}&per_page=30&page=1&sort=recent"
        try:
            resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("data", []) or data.get("data", [])
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = (item.get("title") or item.get("name") or "").strip()
                        if not title:
                            continue

                        # Check status & active registration
                        status = str(item.get("status", "")).lower()
                        if status in ["expired", "closed", "archived", "ended"]:
                            continue

                        days_left = item.get("days_left")
                        if days_left is not None and isinstance(days_left, (int, float)) and days_left < 0:
                            continue

                        reg_end = item.get("end_date") or item.get("regn_end_date") or item.get("registration_end_date")
                        deadline_formatted = format_unstop_date(reg_end)

                        if not is_registration_deadline_active(deadline_formatted):
                            continue

                        # Precise Apply URL
                        seo_url = (item.get("seo_url") or item.get("slug") or "").strip()
                        public_url = item.get("public_url")
                        opp_id = item.get("id")

                        if public_url and str(public_url).startswith("http"):
                            apply_url = str(public_url)
                        elif seo_url:
                            if seo_url.startswith("http"):
                                apply_url = seo_url
                            elif "/" in seo_url:
                                apply_url = f"https://unstop.com/{seo_url}"
                            else:
                                apply_url = f"https://unstop.com/{cat}/{seo_url}"
                        elif opp_id:
                            apply_url = f"https://unstop.com/p/{opp_id}"
                        else:
                            continue

                        if apply_url in seen_urls:
                            continue

                        seen_urls.add(apply_url)
                        org = item.get("organisation", {}).get("name") if isinstance(item.get("organisation"), dict) else "Unstop Partner"

                        # Prizes & Rewards
                        prizes = item.get("prizes", [])
                        prize_text = "Cash Prizes & Certificates"
                        if prizes and isinstance(prizes, list) and len(prizes) > 0:
                            first_prize = prizes[0].get("cash") or prizes[0].get("amount") or prizes[0].get("name")
                            if first_prize:
                                prize_text = f"₹{first_prize:,}" if isinstance(first_prize, (int, float)) else str(first_prize)

                        # Location & Mode
                        region = item.get("region") or item.get("city") or "India / Online"
                        mode = "Online" if "online" in str(item.get("filters", "")).lower() or "online" in region.lower() else "Hybrid / On-site"

                        posted_raw = item.get("created_at") or item.get("start_date") or item.get("published_at")
                        posted_date_str = format_unstop_date(posted_raw) if posted_raw else "Past 24 Hours"

                        hackathons.append({
                            "platform": f"Unstop ({org})",
                            "title": title,
                            "theme": "Engineering & Innovation Challenge",
                            "mode": mode,
                            "location": region,
                            "prize_pool": prize_text,
                            "posted_date": posted_date_str,
                            "registration_deadline": deadline_formatted,
                            "event_dates": "See Event Page",
                            "eligibility": "Engineering Students & Freshers",
                            "apply_url": apply_url,
                            "description": item.get("short_description") or f"Campus and corporate challenge organized by {org} on Unstop: {title}.",
                        })

        except Exception as exc:
            logger.debug("Failed fetching Unstop category %s: %s", cat, exc)

    logger.info("Unstop Collector ingested %d active opportunities", len(hackathons))
    return hackathons
