"""Collector for Devpost Global Hackathons (Recent & Active Registrations)."""

import logging
import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import DEVPOST_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import (
    is_registration_deadline_active,
    is_valid_apply_url,
)

logger = logging.getLogger("techyupdates.collectors.devpost")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Standard Devpost platform routes to ignore as hackathon targets
DEVPOST_SYSTEM_PATHS = {
    "devpost.com",
    "devpost.com/",
    "devpost.com/hackathons",
    "devpost.com/software",
    "devpost.com/rules",
    "devpost.com/about",
    "devpost.com/terms",
    "devpost.com/privacy",
    "devpost.com/login",
    "devpost.com/register",
    "help.devpost.com",
    "info.devpost.com",
}


async def fetch_devpost_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch online and recently added hackathons from Devpost with exact direct challenge subdomains."""
    hackathons: List[Dict[str, Any]] = []
    seen_urls = set()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://devpost.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    # 1. Primary: Scrape curated Devpost search URLs sorted by recently-added and open status
    for url in DEVPOST_CONFIG["search_urls"]:
        try:
            resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug("Devpost search URL %s returned %d", url, resp.status_code)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for all challenge listing cards and links
            cards = soup.select(".challenge-listing, .hackathon-tile, .main-challenge-tile, [data-role='featured_challenge'], article")

            for card in cards:
                # Find direct hackathon subdomain link
                link_elems = card.find_all("a", href=True)
                apply_url = ""
                for l in link_elems:
                    href = l["href"].strip()
                    # Check if it's a devpost subdomain or specific challenge page
                    if "devpost.com" in href:
                        clean_href = href.split("?")[0].rstrip("/")
                        clean_domain = clean_href.replace("https://", "").replace("http://", "")
                        if clean_domain not in DEVPOST_SYSTEM_PATHS and not clean_domain.endswith("/hackathons"):
                            apply_url = href
                            break
                    elif href.startswith("/") and len(href) > 2 and not any(href.startswith(p) for p in ["/hackathons", "/software", "/about"]):
                        apply_url = f"https://devpost.com{href}"
                        break

                if not apply_url or apply_url in seen_urls:
                    continue

                # Title extraction
                title_elem = card.select_one("h2, h3, h4, .title, .main-challenge-tile-title, strong")
                title = title_elem.get_text(strip=True) if title_elem else ""
                if not title or len(title) < 3 or title.lower() in ["devpost", "explore hackathons"]:
                    continue

                # Filter out obsolete past years in title
                if re.search(r"\b201[0-9]\b|\b202[0-4]\b", title):
                    continue

                # Prize extraction
                prize_elem = card.select_one(".prize-amount, .value, .prize, .prize-pool")
                prize_str = prize_elem.get_text(strip=True) if prize_elem else "Cash Prizes & Swag"

                # Deadline extraction
                deadline_elem = card.select_one(".deadline, .submission-period, time, .time-left")
                deadline_str = deadline_elem.get_text(strip=True) if deadline_elem else "Open Registration"
                if not is_registration_deadline_active(deadline_str, title_context=title):
                    continue

                # Mode & Location
                loc_elem = card.select_one(".location, .info .location")
                loc_str = loc_elem.get_text(strip=True) if loc_elem else "Online (Global)"
                mode = "Online" if "online" in loc_str.lower() or "virtual" in loc_str.lower() or "global" in loc_str.lower() else "In-Person"

                # Theme/Description
                desc_elem = card.select_one(".synopsis, .challenge-description, p")
                desc = desc_elem.get_text(strip=True) if desc_elem else f"Developer hackathon on Devpost: {title}."

                seen_urls.add(apply_url)
                hackathons.append({
                    "platform": "Devpost",
                    "title": title,
                    "theme": "AI, Cloud & Global Innovation Challenge",
                    "mode": mode,
                    "location": loc_str,
                    "prize_pool": prize_str,
                    "posted_date": "Past 24 Hours",
                    "registration_deadline": deadline_str,
                    "event_dates": "Active Challenge Period",
                    "eligibility": "Global Developers & Builders",
                    "apply_url": apply_url,
                    "description": desc,
                })
        except Exception as exc:
            logger.debug("Failed Devpost HTML query for %s: %s", url, exc)

    # 2. Secondary: If live scrape yielded few results, also attempt the JSON endpoint
    if len(hackathons) < 3:
        try:
            api_headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Referer": "https://devpost.com/hackathons",
            }
            api_url = "https://devpost.com/api/hackathons?challenge_type[]=online&status[]=open&sort_by=recently-added"
            resp = await client.get(api_url, headers=api_headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("hackathons", []) if isinstance(data, dict) else []
                for item in items:
                    title = (item.get("title") or "").strip()
                    apply_url = (item.get("url") or "").strip()
                    if not title or not apply_url or apply_url in seen_urls:
                        continue
                    if re.search(r"\b201[0-9]\b|\b202[0-4]\b", title):
                        continue

                    deadline_str = item.get("time_left_to_submission") or "Open Registration"
                    if not is_registration_deadline_active(deadline_str, title_context=title):
                        continue

                    prize_str = item.get("prize_amount") or "Cash Prizes & Swag"
                    seen_urls.add(apply_url)
                    hackathons.append({
                        "platform": "Devpost",
                        "title": title,
                        "theme": "AI & Developer Innovation",
                        "mode": "Online",
                        "location": "Global (Online)",
                        "prize_pool": prize_str,
                        "posted_date": "Past 24 Hours",
                        "registration_deadline": deadline_str,
                        "event_dates": item.get("submission_period_dates") or "Active Period",
                        "eligibility": "All Developers Worldwide",
                        "apply_url": apply_url,
                        "description": f"Devpost developer challenge: {title}.",
                    })
        except Exception as exc:
            logger.debug("Failed Devpost JSON fallback: %s", exc)

    logger.info("Devpost Collector ingested %d active hackathons", len(hackathons))
    return hackathons
