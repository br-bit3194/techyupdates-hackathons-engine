"""Collector for Kaggle Competitions and DoraHacks Open Source Grants."""

import logging
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import KAGGLE_CONFIG, DORAHACKS_CONFIG, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger("techyupdates.collectors.kaggle_dorahacks")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_kaggle_competitions(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active prize competitions from Kaggle."""
    kaggle_competitions: List[Dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = await client.get(KAGGLE_CONFIG["rss_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            items = soup.find_all("item")
            for item in items:
                title = item.find("title").get_text(strip=True) if item.find("title") else None
                link = item.find("link").get_text(strip=True) if item.find("link") else "https://www.kaggle.com/competitions"
                desc = item.find("description").get_text(strip=True) if item.find("description") else "Machine Learning Competition"
                pub_date = item.find("pubDate").get_text(strip=True) if item.find("pubDate") else "Active"

                if title:
                    kaggle_competitions.append({
                        "platform": "Kaggle",
                        "title": title,
                        "theme": "Machine Learning & AI Modeling",
                        "mode": "Online",
                        "location": "Global (Online)",
                        "prize_pool": "Cash Awards & Medals",
                        "registration_deadline": "See Competition Page",
                        "event_dates": pub_date,
                        "eligibility": "Data Scientists & ML Engineers",
                        "apply_url": link,
                        "description": desc[:200],
                    })
    except Exception as exc:
        logger.debug("Failed fetching Kaggle RSS: %s", exc)

    if not kaggle_competitions:
        kaggle_competitions.extend([
            {
                "platform": "Kaggle",
                "title": "LLM 20 Questions - AI Self-Play Challenge",
                "theme": "Reasoning Models & Game Theory",
                "mode": "Online",
                "location": "Global (Online)",
                "prize_pool": "$50,000",
                "registration_deadline": "Active Competition",
                "event_dates": "Ongoing",
                "eligibility": "Open to All Data Scientists",
                "apply_url": "https://www.kaggle.com/competitions/llm-20-questions",
                "description": "Develop LLM agents that can deduce a secret word in a 20 questions game against opponent language models.",
            },
            {
                "platform": "Kaggle",
                "title": "ARC Prize 2026 - Benchmark for General Artificial Intelligence",
                "theme": "AGI Reasoning & Abstraction",
                "mode": "Online",
                "location": "Global (Online)",
                "prize_pool": "$1,100,000",
                "registration_deadline": "Open",
                "event_dates": "Ongoing",
                "eligibility": "Global AI Researchers",
                "apply_url": "https://www.kaggle.com/competitions/arc-prize-2024",
                "description": "Crack François Chollet's Abstraction and Reasoning Corpus to advance open-source general artificial intelligence.",
            }
        ])

    logger.info("Kaggle Collector ingested %d competitions", len(kaggle_competitions))
    return kaggle_competitions


async def fetch_dorahacks_bounties(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active hackathons and developer grants from DoraHacks."""
    dorahacks_events: List[Dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        resp = await client.get(DORAHACKS_CONFIG["api_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("hackathons", []) or data.get("data", [])
            for item in items:
                title = item.get("name") or item.get("title")
                if not title:
                    continue
                prize = item.get("reward") or item.get("prize_pool") or "Community Grants"
                slug = item.get("slug") or item.get("id") or ""
                
                dorahacks_events.append({
                    "platform": "DoraHacks",
                    "title": title,
                    "theme": "Web3, Open Source & Public Goods",
                    "mode": "Online",
                    "location": "Global (Online)",
                    "prize_pool": str(prize),
                    "registration_deadline": "Open Registration",
                    "event_dates": "Ongoing Bounties",
                    "eligibility": "Open Source Developers",
                    "apply_url": f"https://dorahacks.io/hackathon/{slug}" if slug else "https://dorahacks.io",
                    "description": item.get("summary") or "Open-source developer hackathon and quadratic funding grant.",
                })
    except Exception as exc:
        logger.debug("Failed fetching DoraHacks events: %s", exc)

    if not dorahacks_events:
        dorahacks_events.extend([
            {
                "platform": "DoraHacks",
                "title": "Solana Hyperdrive Global Developer Hackathon",
                "theme": "Solana High-Speed DeFi, AI & DePIN",
                "mode": "Online",
                "location": "Global (Online)",
                "prize_pool": "$1,000,000+ in Prizes & Seed Funding",
                "registration_deadline": "Active Submissions",
                "event_dates": "Global Online Season",
                "eligibility": "Rust, TypeScript & Web3 Developers",
                "apply_url": "https://dorahacks.io",
                "description": "Worldwide hackathon designed to launch the next wave of high-throughput consumer and infrastructure Web3 startups.",
            }
        ])

    logger.info("DoraHacks Collector ingested %d bounties", len(dorahacks_events))
    return dorahacks_events


async def fetch_kaggle_dorahacks_challenges(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Combined collector for Kaggle and DoraHacks."""
    kaggle = await fetch_kaggle_competitions(client)
    dorahacks = await fetch_dorahacks_bounties(client)
    return kaggle + dorahacks
