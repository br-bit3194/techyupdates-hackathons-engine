"""Collector for Major League Hacking (MLH) and Devfolio Hackathons (Active & Open Now)."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import MLH_CONFIG, DEVFOLIO_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import is_registration_deadline_active

logger = logging.getLogger("techyupdates.collectors.mlh_devfolio")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_mlh_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Scrape upcoming hackathons from MLH Official Season page."""
    mlh_events: List[Dict[str, Any]] = []
    seen_urls = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = await client.get(MLH_CONFIG["base_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".event-wrapper, .event, .inner, .event-card")

            for card in cards:
                title_elem = card.select_one(".event-name, h3, h4")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                link_elem = card.select_one("a.event-link, a[href*='http']") or (card if card.name == 'a' else card.find_parent("a"))
                apply_url = link_elem.get("href") if link_elem else ""
                if not apply_url or apply_url in seen_urls:
                    continue

                date_elem = card.select_one(".event-date, p.date, .date")
                event_date = date_elem.get_text(strip=True) if date_elem else "Upcoming Season Weekend"

                # Check if deadline/event is active
                if not is_registration_deadline_active(event_date):
                    continue

                loc_elem = card.select_one(".event-location, .location")
                loc_str = loc_elem.get_text(strip=True) if loc_elem else "Collegiate / Online"
                mode = "Online" if "digital" in loc_str.lower() or "online" in loc_str.lower() else "In-Person"

                seen_urls.add(apply_url)
                mlh_events.append({
                    "platform": "Major League Hacking (MLH)",
                    "title": title,
                    "theme": "Collegiate & Student Hackathon",
                    "mode": mode,
                    "location": loc_str,
                    "prize_pool": "Swag, Hardware & Sponsor Bounties",
                    "posted_date": "Active Season Event",
                    "registration_deadline": "Open Registration",
                    "event_dates": event_date,
                    "eligibility": "University & High School Students",
                    "apply_url": apply_url,
                    "description": f"Official MLH Member Hackathon with developer workshops, mentorship, and sponsor tracks: {title}.",
                })
    except Exception as exc:
        logger.debug("Failed fetching MLH events: %s", exc)

    logger.info("MLH Collector ingested %d hackathons", len(mlh_events))
    return mlh_events


async def fetch_devfolio_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active and upcoming hackathons from Devfolio public API."""
    devfolio_events: List[Dict[str, Any]] = []
    seen_slugs = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://devfolio.co/hackathons",
        "Origin": "https://devfolio.co",
    }

    filters = ["open_now", "upcoming", "all"]
    for f in filters:
        try:
            url = f"https://api.devfolio.co/api/hackathons?filter={f}"
            resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("result", []) or data.get("hackathons", [])
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name", "").strip()
                        slug = item.get("slug", "").strip()
                        if not name or not slug or slug in seen_slugs:
                            continue

                        # Check if active / open
                        app_close = item.get("applications_close_at") or item.get("ends_at") or item.get("starts_at")
                        deadline_str = "Open Registration"
                        if app_close:
                            try:
                                dt = datetime.fromisoformat(str(app_close).replace("Z", "+00:00"))
                                deadline_str = dt.strftime("%b %d, %Y")
                            except Exception:
                                deadline_str = str(app_close)[:10]

                        if not is_registration_deadline_active(deadline_str):
                            continue

                        prizes = item.get("prizes", {})
                        prize_str = prizes.get("desc") if isinstance(prizes, dict) else "Community Grants & Bounties"
                        if not prize_str:
                            prize_str = "Community Grants & Swag"

                        is_online = item.get("is_online", True)
                        mode = "Online" if is_online else "In-Person"
                        location = item.get("location") or ("Global / Online" if is_online else "India (In-Person)")

                        # Exact direct apply link
                        apply_url = f"https://{slug}.devfolio.co"

                        posted_dt_raw = item.get("published_at") or item.get("created_at") or item.get("starts_at")
                        posted_str = str(posted_dt_raw)[:10] if posted_dt_raw else "Past 24 Hours"

                        seen_slugs.add(slug)
                        devfolio_events.append({
                            "platform": "Devfolio",
                            "title": name,
                            "theme": "Web3, Open Source & Developer Innovation",
                            "mode": mode,
                            "location": location,
                            "prize_pool": prize_str,
                            "posted_date": posted_str,
                            "registration_deadline": deadline_str,
                            "event_dates": str(item.get("starts_at", "Upcoming"))[:10],
                            "eligibility": "All Developers & Web3 Builders",
                            "apply_url": apply_url,
                            "description": item.get("tagline") or f"Community hackathon hosted on Devfolio: {name}.",
                        })
        except Exception as exc:
            logger.debug("Failed fetching Devfolio filter %s: %s", f, exc)

    logger.info("Devfolio Collector ingested %d hackathons", len(devfolio_events))
    return devfolio_events


async def fetch_mlh_devfolio_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Combined collector for MLH and Devfolio."""
    mlh = await fetch_mlh_hackathons(client)
    devfolio = await fetch_devfolio_hackathons(client)
    return mlh + devfolio
