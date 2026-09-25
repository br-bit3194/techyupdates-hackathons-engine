"""Collector for HackerEarth Competitions and Superteam Earn Web3/AI Bounties."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from config.targets import HACKEREARTH_CONFIG, REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import is_registration_deadline_active

logger = logging.getLogger("techyupdates.collectors.hackerearth_superteam")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_hackerearth_challenges(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch live and upcoming challenges from HackerEarth official public API."""
    challenges: List[Dict[str, Any]] = []
    seen_urls = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.hackerearth.com/challenges/",
    }

    try:
        resp = await client.get(HACKEREARTH_CONFIG["api_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            sections = ["response", "upcoming", "ongoing"]
            items: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                for sec in sections:
                    if isinstance(data.get(sec), list):
                        items.extend(data[sec])
            elif isinstance(data, list):
                items = data

            for item in items:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or item.get("name") or "").strip()
                apply_url = (item.get("url") or item.get("challenge_url") or "").strip()
                if not title or not apply_url or apply_url in seen_urls:
                    continue

                if not apply_url.startswith("http"):
                    apply_url = f"https://www.hackerearth.com{apply_url}"

                # Status check
                status = str(item.get("status", "")).lower()
                if status in ["ended", "closed", "past"]:
                    continue

                # Registration end
                end_time = item.get("end_tz") or item.get("end_datetime") or item.get("end_time")
                deadline_str = "Open Registration"
                if end_time:
                    try:
                        dt = datetime.fromisoformat(str(end_time).replace("Z", "+00:00"))
                        deadline_str = dt.strftime("%b %d, %Y")
                    except Exception:
                        deadline_str = str(end_time)[:10]

                if not is_registration_deadline_active(deadline_str):
                    continue

                challenge_type = item.get("challenge_type") or "Hackathon"
                is_hiring = "hiring" in str(challenge_type).lower() or "hiring" in title.lower()

                seen_urls.add(apply_url)
                challenges.append({
                    "platform": f"HackerEarth ({challenge_type})",
                    "title": title,
                    "theme": "Software Engineering & Competitive Coding" if not is_hiring else "Developer Hiring Sprint & PPI",
                    "mode": "Online",
                    "location": "Global / India (Online)",
                    "prize_pool": "Cash Prizes, Job Offers & Swag" if is_hiring else "Cash Rewards & Tech Bounties",
                    "posted_date": str(item.get("start_tz") or "Past 24 Hours")[:10],
                    "registration_deadline": deadline_str,
                    "event_dates": item.get("start_tz") or "Active Period",
                    "eligibility": "Developers, Freshers & Engineering Students",
                    "apply_url": apply_url,
                    "description": item.get("description") or f"National engineering challenge and coding sprint hosted on HackerEarth: {title}.",
                })
    except Exception as exc:
        logger.debug("Failed fetching HackerEarth challenges: %s", exc)

    logger.info("HackerEarth Collector ingested %d challenges", len(challenges))
    return challenges


async def fetch_superteam_bounties(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active developer bounties from Superteam Earn."""
    bounties: List[Dict[str, Any]] = []
    seen_slugs = set()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": "https://earn.superteam.fun/",
    }

    try:
        url = "https://earn.superteam.fun/api/listings?type=bounties&status=open"
        resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("listings", []) or data.get("data", [])
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = (item.get("title") or "").strip()
                    slug = (item.get("slug") or "").strip()
                    if not title or not slug or slug in seen_slugs:
                        continue

                    reward_amount = item.get("rewardAmount") or item.get("totalReward") or ""
                    token = item.get("token") or "USDC"
                    prize_str = f"${reward_amount:,} {token}" if isinstance(reward_amount, (int, float)) else f"{reward_amount} {token}"
                    if not str(reward_amount).strip():
                        prize_str = "USDC Developer Grants & Bounties"

                    deadline_str = str(item.get("deadline", "Open"))[:10]
                    if not is_registration_deadline_active(deadline_str):
                        continue

                    apply_url = f"https://earn.superteam.fun/listings/bounties/{slug}"
                    seen_slugs.add(slug)

                    bounties.append({
                        "platform": "Superteam Earn",
                        "title": title,
                        "theme": "Solana & Open Source Web3 Bounties",
                        "mode": "Online",
                        "location": "Global (Online)",
                        "prize_pool": prize_str,
                        "posted_date": "Past 24 Hours",
                        "registration_deadline": deadline_str,
                        "event_dates": "Active Bounty Sprint",
                        "eligibility": "Rust, TypeScript & Web3 Developers",
                        "apply_url": apply_url,
                        "description": item.get("shortDescription") or f"Developer buildathon and open grant hosted on Superteam Earn: {title}.",
                    })
    except Exception as exc:
        logger.debug("Failed fetching Superteam Earn: %s", exc)

    logger.info("Superteam Collector ingested %d bounties", len(bounties))
    return bounties


async def fetch_hackerearth_superteam_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Combined collector for HackerEarth and Superteam Earn."""
    he = await fetch_hackerearth_challenges(client)
    st = await fetch_superteam_bounties(client)
    return he + st
