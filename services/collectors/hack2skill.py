"""Collector for Hack2skill Indian & Global Developer Hackathons (Active & Direct Event URLs Only)."""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from config.targets import HACK2SKILL_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import (
    is_registration_deadline_active,
    is_direct_hackathon_url,
    parse_date_heuristic,
)

logger = logging.getLogger("techyupdates.collectors.hack2skill")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_hack2skill_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active and open hackathons from Hack2skill with exact direct event URLs."""
    hackathons: List[Dict[str, Any]] = []
    seen_urls = set()
    now_utc = datetime.now(timezone.utc)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://hack2skill.com/hackathons-listing",
        "Origin": "https://hack2skill.com",
    }

    # 1. Query Official Public REST API
    try:
        api_url = HACK2SKILL_CONFIG["api_url"]
        resp = await client.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("data", {}).get("records", []) if isinstance(data.get("data"), dict) else (data.get("data") or data.get("records") or [])
            if isinstance(events, list):
                for item in events:
                    if not isinstance(item, dict):
                        continue
                    title = (item.get("title") or "").strip()
                    if not title or len(title) < 3:
                        continue

                    # Check status & active publishing
                    status = str(item.get("status", "")).upper()
                    if status in ["UNPUBLISHED", "DRAFT", "CLOSED", "ENDED", "ARCHIVED"]:
                        continue
                    if item.get("isLive") is False or item.get("isPublished") is False:
                        continue

                    # Construct exact event direct link
                    custom_url = (item.get("customEventUrl") or "").strip()
                    event_slug = (item.get("eventUrl") or item.get("slug") or "").strip()

                    if custom_url and custom_url.startswith("http"):
                        apply_url = custom_url
                    elif event_slug:
                        apply_url = f"https://hack2skill.com/event/{event_slug}"
                    else:
                        continue

                    # Verify that the URL is a direct hackathon link, not an index/filter page
                    if not is_direct_hackathon_url(apply_url) or apply_url in seen_urls:
                        continue

                    # Registration Deadline & Active Status check
                    reg_end = item.get("registrationEnd") or item.get("endDate") or item.get("eventEnd")
                    deadline_str = "Open Registration"
                    if reg_end:
                        parsed_end = parse_date_heuristic(str(reg_end))
                        if parsed_end:
                            if parsed_end.date() < now_utc.date():
                                continue  # Registration closed
                            deadline_str = parsed_end.strftime("%d %b %Y")
                        else:
                            deadline_str = str(reg_end)[:10]

                    if not is_registration_deadline_active(deadline_str, title_context=title):
                        continue

                    # Mode & Location
                    tags = item.get("tags") or {}
                    mode_val = ""
                    if isinstance(tags, dict):
                        mode_val = (tags.get("mode") or {}).get("value", "") if isinstance(tags.get("mode"), dict) else str(tags.get("mode") or "")
                    mode = "Online" if "online" in mode_val.lower() or "virtual" in mode_val.lower() or not mode_val else "Hybrid / On-site"

                    # Description / Theme
                    desc = item.get("shortDescription") or item.get("description") or f"National innovation challenge and developer hackathon on Hack2skill: {title}"
                    if len(desc) > 300:
                        desc = desc[:297] + "..."

                    # Prize Pool
                    prize_text = "Cash Rewards & Mentorship"
                    if item.get("prizePool"):
                        prize_text = str(item["prizePool"])
                    elif isinstance(tags, dict) and tags.get("ticket"):
                        ticket_info = tags["ticket"].get("value") if isinstance(tags["ticket"], dict) else tags["ticket"]
                        prize_text = f"Free Entry • {ticket_info}" if ticket_info else prize_text

                    posted_raw = item.get("startDate") or item.get("createdAt") or item.get("eventStart")
                    posted_date_str = str(posted_raw)[:10] if posted_raw else "Past 24 Hours"

                    seen_urls.add(apply_url)
                    hackathons.append({
                        "platform": "Hack2skill",
                        "title": title,
                        "theme": "Enterprise & Tech Innovation Challenge",
                        "mode": mode,
                        "location": mode_val or "India (Online)",
                        "prize_pool": prize_text,
                        "posted_date": posted_date_str,
                        "registration_deadline": deadline_str,
                        "event_dates": "See Event Page",
                        "eligibility": "Students & Professional Developers",
                        "apply_url": apply_url,
                        "description": desc,
                    })
    except Exception as exc:
        logger.debug("Failed querying Hack2skill public API: %s", exc)

    logger.info("Hack2skill Collector ingested %d live verified hackathons", len(hackathons))
    return hackathons
