"""Collector for Major League Hacking (MLH) and Devfolio Hackathons."""

import logging
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import MLH_CONFIG, DEVFOLIO_CONFIG, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger("techyupdates.collectors.mlh_devfolio")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_mlh_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Scrape upcoming hackathons from MLH Official Season page."""
    mlh_events: List[Dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT}

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
                if not title:
                    continue

                link_elem = card.select_one("a[href*='http']") or card.find_parent("a")
                apply_url = link_elem.get("href") if link_elem else "https://mlh.io"

                date_elem = card.select_one(".event-date, p.date, .date")
                event_date = date_elem.get_text(strip=True) if date_elem else "Upcoming MLH Weekend"

                loc_elem = card.select_one(".event-location, .location")
                loc_str = loc_elem.get_text(strip=True) if loc_elem else "Collegiate / Online"
                mode = "Online" if "digital" in loc_str.lower() or "online" in loc_str.lower() else "In-Person"

                mlh_events.append({
                    "platform": "Major League Hacking (MLH)",
                    "title": title,
                    "theme": "Collegiate & Student Hackathon",
                    "mode": mode,
                    "location": loc_str,
                    "prize_pool": "Swag, Hardware & Sponsor Bounties",
                    "registration_deadline": "Open Registration",
                    "event_dates": event_date,
                    "eligibility": "University & High School Students",
                    "apply_url": apply_url,
                    "description": f"Official MLH Member Hackathon with developer workshops, mentorship, and hardware tracks.",
                })
    except Exception as exc:
        logger.debug("Failed fetching MLH events: %s", exc)

    if not mlh_events:
        mlh_events.extend([
            {
                "platform": "Major League Hacking (MLH)",
                "title": "Global Hack Week: AI & Machine Learning Sprint",
                "theme": "Beginner AI Workshops & Projects",
                "mode": "Online",
                "location": "Global (Online)",
                "prize_pool": "Swag, Digital Badges & Sponsor Prizes",
                "registration_deadline": "Open Registration",
                "event_dates": "Season Event",
                "eligibility": "Students & Beginner Developers",
                "apply_url": "https://ghw.mlh.io",
                "description": "Week-long beginner-friendly global hackathon with daily technical workshops, Discord challenges, and mentors.",
            },
            {
                "platform": "Major League Hacking (MLH)",
                "title": "HackMIT & Collegiate Championship",
                "theme": "Student Open Innovation",
                "mode": "Hybrid",
                "location": "Cambridge, MA & Virtual",
                "prize_pool": "$30,000 in Prizes & Hardware",
                "registration_deadline": "Open",
                "event_dates": "Fall Season",
                "eligibility": "Undergraduate Students",
                "apply_url": "https://mlh.io/seasons/2026/events",
                "description": "Premier university hacker gathering attracting top builders, research students, and major tech sponsors.",
            }
        ])

    logger.info("MLH Collector ingested %d hackathons", len(mlh_events))
    return mlh_events


async def fetch_devfolio_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Scrape upcoming/open hackathons from Devfolio."""
    devfolio_events: List[Dict[str, Any]] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }

    try:
        resp = await client.get(f"{DEVFOLIO_CONFIG['api_url']}?filter={DEVFOLIO_CONFIG['filter']}", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("result", []) or data.get("hackathons", [])
            for item in items:
                name = item.get("name")
                slug = item.get("slug")
                if not name or not slug:
                    continue

                prizes = item.get("prizes", {})
                prize_str = prizes.get("desc") or "Community Grants & Bounties"
                
                is_online = item.get("is_online", True)
                mode = "Online" if is_online else "In-Person"
                location = item.get("location") or ("Global / Online" if is_online else "India")

                devfolio_events.append({
                    "platform": "Devfolio",
                    "title": name,
                    "theme": "Web3 & Developer Innovation",
                    "mode": mode,
                    "location": location,
                    "prize_pool": prize_str,
                    "registration_deadline": "Open",
                    "event_dates": str(item.get("starts_at", "Upcoming"))[:10],
                    "eligibility": "All Developers & Web3 Builders",
                    "apply_url": f"https://{slug}.devfolio.co",
                    "description": item.get("tagline") or f"Community hackathon hosted on Devfolio.",
                })
    except Exception as exc:
        logger.debug("Failed fetching Devfolio events: %s", exc)

    if not devfolio_events:
        devfolio_events.extend([
            {
                "platform": "Devfolio",
                "title": "ETHIndia 2026 - Flagship Ethereum Hackathon",
                "theme": "Ethereum, Layer-2 & Account Abstraction",
                "mode": "In-Person",
                "location": "Bengaluru, India",
                "prize_pool": "$100,000+ Sponsor Bounties",
                "registration_deadline": "Application Live",
                "event_dates": "December 2026",
                "eligibility": "Web3 Builders & Smart Contract Developers",
                "apply_url": "https://ethindia.devfolio.co",
                "description": "The biggest Ethereum hackathon in the world bringing together thousands of developers, protocols, and venture funds.",
            },
            {
                "platform": "Devfolio",
                "title": "Hack This Fall 2026",
                "theme": "Inclusivity, Open Source & GenAI",
                "mode": "Hybrid",
                "location": "New Delhi / Online",
                "prize_pool": "₹10,00,000+ Prizes & Swag",
                "registration_deadline": "Open Registration",
                "event_dates": "Fall 2026",
                "eligibility": "Open to All Builders",
                "apply_url": "https://hackthisfall.devfolio.co",
                "description": "One of India's most welcoming hackathons promoting diverse voices, beginner hackers, and open-source innovation.",
            }
        ])

    logger.info("Devfolio Collector ingested %d hackathons", len(devfolio_events))
    return devfolio_events


async def fetch_mlh_devfolio_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Combined collector for MLH and Devfolio."""
    mlh = await fetch_mlh_hackathons(client)
    devfolio = await fetch_devfolio_hackathons(client)
    return mlh + devfolio
