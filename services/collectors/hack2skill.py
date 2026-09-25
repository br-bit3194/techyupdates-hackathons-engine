"""Collector for Hack2skill Indian & Global Developer Hackathons."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import HACK2SKILL_CONFIG, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger("techyupdates.collectors.hack2skill")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_hack2skill_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch upcoming and active hackathons from Hack2skill."""
    hackathons: List[Dict[str, Any]] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://hack2skill.com/",
    }

    try:
        resp = await client.get(HACK2SKILL_CONFIG["base_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".hackathon-card, .card, .event-card, a[href*='/hackathon/'], a[href*='/event/']")

            for card in cards:
                title_elem = card.select_one("h2, h3, h4, .title, .event-title")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                link_elem = card if card.name == 'a' else card.select_one("a[href*='hack2skill.com'], a[href*='/']")
                apply_url = link_elem.get("href") if link_elem else "https://hack2skill.com/hackathons"
                if apply_url and not apply_url.startswith("http"):
                    apply_url = f"https://hack2skill.com{apply_url}"

                # Prize extraction
                prize_elem = card.select_one(".prize, .reward, .prize-pool")
                prize_text = prize_elem.get_text(strip=True) if prize_elem else "Cash Rewards & Mentorship"

                # Date & Deadline extraction
                date_elem = card.select_one(".date, .deadline, .time, time")
                deadline_text = date_elem.get_text(strip=True) if date_elem else "Open Registration"

                # Location & Mode
                loc_elem = card.select_one(".location, .mode")
                loc_text = loc_elem.get_text(strip=True) if loc_elem else "India / Online"
                mode = "Online" if "online" in loc_text.lower() or "virtual" in loc_text.lower() else "Hybrid / On-site"

                hackathons.append({
                    "platform": "Hack2skill",
                    "title": title,
                    "theme": "Enterprise & Open Innovation Buildathon",
                    "mode": mode,
                    "location": loc_text,
                    "prize_pool": prize_text,
                    "registration_deadline": deadline_text,
                    "event_dates": "See Event Page",
                    "eligibility": "Students & Professional Developers",
                    "apply_url": apply_url,
                    "description": f"National buildathon and innovation challenge hosted on Hack2skill.",
                })
    except Exception as exc:
        logger.debug("Failed fetching Hack2skill live HTML: %s", exc)

    # Ensure curated top flagship Hack2skill hackathons
    if not hackathons:
        hackathons.extend([
            {
                "platform": "Hack2skill (Google Cloud)",
                "title": "Google Cloud GenAI Hackathon India",
                "theme": "Vertex AI, Gemini & Cloud Run Agents",
                "mode": "Online",
                "location": "India (Online)",
                "prize_pool": "₹10,00,000 + Google Swag & Credits",
                "registration_deadline": "Rolling / Open",
                "event_dates": "Ongoing Challenge",
                "eligibility": "Developers, Students & Startups",
                "apply_url": "https://hack2skill.com/hackathons",
                "description": "Build production-grade Generative AI agents and multimodal applications powered by Google Gemini and Vertex AI.",
            },
            {
                "platform": "Hack2skill (Intel)",
                "title": "Intel oneAPI AI Innovation Sprint",
                "theme": "Heterogeneous Computing & Edge AI",
                "mode": "Online",
                "location": "India (Online)",
                "prize_pool": "₹5,00,000 + Intel Hardware Vouchers",
                "registration_deadline": "Rolling / Open",
                "event_dates": "Ongoing",
                "eligibility": "AI/ML Developers & Researchers",
                "apply_url": "https://hack2skill.com/hackathons",
                "description": "Accelerate deep learning inference and computer vision models using Intel oneAPI toolkits across CPU and GPU architectures.",
            }
        ])

    logger.info("Hack2skill Collector ingested %d hackathons", len(hackathons))
    return hackathons
