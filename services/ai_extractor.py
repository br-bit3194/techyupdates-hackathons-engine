"""AI Extraction & Categorization Engine for Hackathons using Google Gemini Flash and Pydantic."""

import os
import json
import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("techyupdates.ai_extractor")


class HackathonRecord(BaseModel):
    """Structured contract for normalized hackathon & competition records."""
    platform: str = Field(description="Host platform or organizing entity (e.g., 'Devpost', 'Unstop', 'Google', 'Devfolio')")
    title: str = Field(description="Normalized hackathon or competition title")
    category: Literal[
        "AI & GenAI Hackathons",
        "Web3 & Open Source Hackathons",
        "Student & University Hackathons",
        "Open Innovation & Hiring Challenges",
    ] = Field(description="Target category for spreadsheet tab grouping")
    theme: str = Field(description="Primary technical domain or track (e.g., 'GenAI Agents', 'DeFi', 'System Architecture')")
    mode: Literal["Online", "In-Person", "Hybrid"] = Field(description="Event mode")
    location: str = Field(description="Geographic venue or 'Global (Online)'")
    prize_pool: str = Field(description="Prize pool or rewards (e.g. '$100,000', '₹15,00,000', 'Grants & Swag')")
    registration_deadline: str = Field(description="Formatted registration deadline (e.g. '15 Oct 2026' or 'Open Registration')")
    event_dates: str = Field(description="Scheduled dates or 'See Event Page'")
    eligibility: str = Field(description="Target audience (e.g., 'All Developers', 'College Students', 'Open to All')")
    why_participate: str = Field(description="1-line crisp reason highlighting why this event is high signal (prizes, hiring PPI, mentorship)")
    apply_url: str = Field(description="Direct registration link")


class HackathonsBatch(BaseModel):
    items: List[HackathonRecord]


def fallback_classify_hackathon(raw: Dict[str, Any]) -> HackathonRecord:
    """Rule-based heuristic classifier used when Gemini AI is unreachable or quota exhausted."""
    title = raw.get("title", "").strip()
    platform = raw.get("platform", "Devpost").strip()
    location = raw.get("location", "Global (Online)").strip()
    apply_url = raw.get("apply_url", "").strip()
    desc = raw.get("description", "").lower()
    prize = raw.get("prize_pool", "Prizes & Swag").strip()
    t_lower = title.lower()
    corpus = f"{t_lower} {desc} {platform.lower()}"

    # 1. Category Classification
    if any(k in corpus for k in ["genai", "llm", "agent", "prompt", "rag", "langchain", "gpt", "vertex", "gemini", "vision", "kaggle", "machine learning", "deep learning", "nlp", "data science"]):
        category = "AI & GenAI Hackathons"
        theme = "Generative AI & Intelligent Agents"
    elif any(k in corpus for k in ["web3", "crypto", "ethereum", "solana", "defi", "blockchain", "smart contract", "dorahacks", "bounty", "grant", "open source", "public goods"]):
        category = "Web3 & Open Source Hackathons"
        theme = "Web3 Infrastructure & Open Source Tools"
    elif any(k in corpus for k in ["mlh", "major league hacking", "collegiate", "university", "campus", "college", "student", "beginner", "freshers", "hackmit", "techfest", "devfolio"]):
        category = "Student & University Hackathons"
        theme = "Collegiate Innovation & Student Projects"
    else:
        category = "Open Innovation & Hiring Challenges"
        theme = "Corporate Innovation & Engineering Sprints"

    # 2. Mode Detection
    loc_lower = location.lower()
    if "hybrid" in loc_lower or "hybrid" in corpus:
        mode: Literal["Online", "In-Person", "Hybrid"] = "Hybrid"
    elif "online" in loc_lower or "virtual" in loc_lower or "remote" in loc_lower or "global" in loc_lower:
        mode = "Online"
    else:
        mode = "In-Person"

    # 3. Why participate summary
    if "ppi" in corpus or "hiring" in corpus or "interview" in corpus:
        why = f"Direct fast-track interview opportunities, cash rewards ({prize}), and industry exposure."
    elif "ai" in category.lower():
        why = f"Massive prize pool ({prize}), cutting-edge AI mentor feedback, and cloud API credits."
    elif "student" in category.lower():
        why = f"Beginner-friendly hacker community, hands-on workshops, hardware bounties, and swag."
    else:
        why = f"Valuable global developer networking, prize grants ({prize}), and portfolio showcase."

    return HackathonRecord(
        platform=platform,
        title=title or "Global Developer Hackathon",
        category=category,
        theme=raw.get("theme") or theme,
        mode=mode,
        location=location,
        prize_pool=prize,
        registration_deadline=raw.get("registration_deadline") or "Open Registration",
        event_dates=raw.get("event_dates") or "See Event Page",
        eligibility=raw.get("eligibility") or ("Students & Developers" if category == "Student & University Hackathons" else "All Developers"),
        why_participate=why,
        apply_url=apply_url,
    )


async def extract_and_tier_hackathons(raw_items: List[Dict[str, Any]], batch_size: int = 50) -> List[HackathonRecord]:
    """Process raw hackathons through Google Gemini hierarchy with automatic fallback."""
    if not raw_items:
        return []

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.warning("[AI] GEMINI_API_KEY not found in environment. Using rule-based fallback for all items.")
        return [fallback_classify_hackathon(item) for item in raw_items]

    # Model Cascade Order
    model_cascade = [
        os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-2.5-flash",
    ]
    # Deduplicate while preserving order
    seen = set()
    models_to_try = [m for m in model_cascade if not (m in seen or seen.add(m))]

    batches = [raw_items[i : i + batch_size] for i in range(0, len(raw_items), batch_size)]
    enriched_results: List[HackathonRecord] = []

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gemini_api_key)
    except Exception as exc:
        logger.error("[AI] Failed initializing Google GenAI Client: %s. Using heuristic fallback.", exc)
        return [fallback_classify_hackathon(item) for item in raw_items]

    system_instruction = """You are the Lead Hackathon Curator & Intelligence Architect for TechyUpdates.
Your task is to analyze raw hackathon listings and return structured, strictly typed HackathonRecord JSON items.
Standardize:
1. category: MUST be one of:
   - 'AI & GenAI Hackathons' (GenAI, LLMs, Agents, Vision, Machine Learning, Kaggle)
   - 'Web3 & Open Source Hackathons' (Blockchain, Smart Contracts, Crypto, DoraHacks, Public Goods)
   - 'Student & University Hackathons' (MLH, Devfolio collegiate, Campus hackathons, Beginner friendly)
   - 'Open Innovation & Hiring Challenges' (Corporate challenges, Unstop, Cash prize tournaments, Hiring sprints)
2. mode: 'Online', 'In-Person', or 'Hybrid'
3. prize_pool: Extract exact rewards (e.g. '$100,000', '₹15,00,000', 'Swag & Mentorship', or 'Grants')
4. why_participate: A punchy 1-sentence value hook highlighting prizes, recruitment opportunities, or tech stack.
Return a valid JSON object adhering to HackathonsBatch schema with an 'items' array.
"""

    for b_idx, batch in enumerate(batches, start=1):
        logger.info("[AI] Processing batch %d/%d (%d items)...", b_idx, len(batches), len(batch))
        batch_prompt = f"Categorize and normalize these {len(batch)} hackathon items:\n" + json.dumps(batch, indent=2)

        batch_success = False
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=batch_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=HackathonsBatch,
                        temperature=0.1,
                    ),
                )
                if response and response.text:
                    parsed_batch = HackathonsBatch.model_validate_json(response.text)
                    enriched_results.extend(parsed_batch.items)
                    logger.info("  ✓ Batch %d processed successfully via %s (%d records)", b_idx, model_name, len(parsed_batch.items))
                    batch_success = True
                    break
            except Exception as exc:
                logger.warning("  ⚠ Model %s failed for batch %d: %s. Trying next model...", model_name, b_idx, exc)
                await asyncio.sleep(1.0)

        if not batch_success:
            logger.error("  ❌ All Gemini models failed for batch %d. Engaging local fallback classifier.", b_idx)
            for item in batch:
                enriched_results.append(fallback_classify_hackathon(item))

        # Respect API rate pacing
        if b_idx < len(batches):
            await asyncio.sleep(3.0)

    logger.info("[AI] Enrichment complete: %d records processed", len(enriched_results))
    return enriched_results
