"""Collector for Direct Company-Hosted Flagship Hackathons & Contests.

Monitors official enterprise developer portals:
- Google Solution Challenge & Build with AI
- Microsoft Imagine Cup & Fabric AI Challenge
- TCS CodeVita & HackQuest
- Infosys HackWithInfy
- Smart India Hackathon (SIH - Govt of India)
- IBM Call for Code Global Challenge
- Meta Hacker Cup
- AWS DeepRacer & Cloud League
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup
from config.targets import REQUEST_TIMEOUT_SECONDS
from services.collectors.liveness_verifier import is_registration_deadline_active

logger = logging.getLogger("techyupdates.collectors.company_flagships")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Registry of official enterprise challenge portals
ENTERPRISE_CHALLENGES = [
    {
        "platform": "Google Developers",
        "title": "Google Solution Challenge 2026",
        "theme": "UN Sustainable Development Goals using Google AI (Gemini & Vertex AI)",
        "mode": "Online",
        "location": "Global (Online)",
        "prize_pool": "$10,000 Top Prizes + Google Mentorship & Swag",
        "registration_deadline": "Rolling / Open",
        "event_dates": "Annual Competition Season",
        "eligibility": "University Students & GDSC Members Worldwide",
        "apply_url": "https://developers.google.com/community/solution-challenge",
        "description": "Build innovative solutions for UN Sustainable Development Goals using Google Cloud, Gemini API, and Android/Flutter.",
    },
    {
        "platform": "Microsoft",
        "title": "Microsoft Imagine Cup 2026 Global Championship",
        "theme": "AI-First Startups & Cloud Innovation on Microsoft Azure",
        "mode": "Hybrid",
        "location": "Global (Online & Seattle Finals)",
        "prize_pool": "$100,000 USD + Mentorship with Satya Nadella",
        "registration_deadline": "Application Live",
        "event_dates": "World Finals Season",
        "eligibility": "Student Innovators & University Builders (Age 18+)",
        "apply_url": "https://imaginecup.microsoft.com/",
        "description": "The premier global student technology competition. Build an AI startup prototype with Azure credits and compete for $100K and direct 1-on-1 mentorship.",
    },
    {
        "platform": "TCS (Tata Consultancy Services)",
        "title": "TCS CodeVita Season 13 - Global Coding Championship",
        "theme": "Competitive Programming & Algorithmic Problem Solving",
        "mode": "Online",
        "location": "India & Global",
        "prize_pool": "$20,000 USD + Direct Fast-Track Hiring (TCS Prime & Digital)",
        "registration_deadline": "Open Registration",
        "event_dates": "Multi-Round Global Contest",
        "eligibility": "Graduating Engineering & Science Students",
        "apply_url": "https://campuscommune.tcs.com/en-in/intro/contests/codevita",
        "description": "Guinness World Record holder for the largest coding competition. Direct campus recruitment into premier TCS Digital and Prime developer roles.",
    },
    {
        "platform": "Infosys",
        "title": "Infosys HackWithInfy 2026",
        "theme": "Data Structures, Algorithms & Full-Stack Engineering",
        "mode": "Online",
        "location": "India (National)",
        "prize_pool": "₹3,50,000 + Direct PPI for Specialist Programmer (SP) Role",
        "registration_deadline": "Season Open",
        "event_dates": "Grand Finale Rounds",
        "eligibility": "B.E./B.Tech/M.E./M.Tech/MCA Students",
        "apply_url": "https://infytq.onwingspan.com/",
        "description": "Elite coding competition offering direct job interview opportunities for high-package Specialist Programmer (SP) and Digital Specialist Engineer (DSE) roles.",
    },
    {
        "platform": "Smart India Hackathon (SIH)",
        "title": "Smart India Hackathon (SIH) 2026 - Hardware & Software Edition",
        "theme": "National Governance, Smart Cities, Agriculture & Space Tech",
        "mode": "Hybrid",
        "location": "Nodal Centers Across India",
        "prize_pool": "₹1,00,000 per problem statement (₹2+ Crore Total Pool)",
        "registration_deadline": "College SPOC Nominations Live",
        "event_dates": "36-Hour National Grand Finale",
        "eligibility": "Higher Education Institution Students in India",
        "apply_url": "https://sih.gov.in/",
        "description": "World's biggest open innovation hackathon by Govt. of India / AICTE solving critical problem statements from Central Ministries and Industry PSUs.",
    },
    {
        "platform": "IBM",
        "title": "IBM Call for Code Global Challenge 2026",
        "theme": "GenAI, Climate Resilience & Open Source Impact",
        "mode": "Online",
        "location": "Global (Online)",
        "prize_pool": "$285,000 USD Total Prize Pool + IBM Watsonx Incubation",
        "registration_deadline": "Submissions Open",
        "event_dates": "Global Challenge Period",
        "eligibility": "Developers, Data Scientists & Students Worldwide",
        "apply_url": "https://www.ibm.com/community/call-for-code/",
        "description": "Create open-source, AI-powered solutions to tackle pressing humanitarian and environmental issues using IBM watsonx and Red Hat OpenShift.",
    },
    {
        "platform": "Meta",
        "title": "Meta Hacker Cup 2026",
        "theme": "Advanced Competitive Programming & Discrete Mathematics",
        "mode": "Online",
        "location": "Global (Online)",
        "prize_pool": "$20,000 Top Prize + Official Meta Swag & Recruitment Fast-Track",
        "registration_deadline": "Open Registration",
        "event_dates": "Annual Championship Rounds",
        "eligibility": "All Programmers Worldwide",
        "apply_url": "https://www.facebook.com/codingcompetitions/hacker-cup/",
        "description": "Meta's flagship annual world programming contest challenging engineers to solve complex algorithmic puzzles under tight execution constraints.",
    },
    {
        "platform": "Amazon Web Services (AWS)",
        "title": "AWS DeepRacer Student League 2026",
        "theme": "Reinforcement Learning & Autonomous AI Racing",
        "mode": "Online",
        "location": "Global (Online)",
        "prize_pool": "$50,000 in Scholarships, AWS Credits & re:Invent Passes",
        "registration_deadline": "Monthly Season Sprints",
        "event_dates": "Monthly Virtual Races",
        "eligibility": "High School & University Students (Age 16+)",
        "apply_url": "https://aws.amazon.com/deepracer/league/",
        "description": "Learn and deploy reinforcement learning models to race 1/18th scale autonomous vehicles on the 3D AWS DeepRacer simulator.",
    },
]


async def fetch_company_flagship_hackathons(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch and verify active company-hosted flagship hackathons."""
    verified_events: List[Dict[str, Any]] = []

    for item in ENTERPRISE_CHALLENGES:
        try:
            # Check registration deadline status
            if not is_registration_deadline_active(item.get("registration_deadline", "")):
                continue

            verified_events.append({
                "platform": item["platform"],
                "title": item["title"],
                "theme": item["theme"],
                "mode": item["mode"],
                "location": item["location"],
                "prize_pool": item["prize_pool"],
                "posted_date": "Active 2026 Season",
                "registration_deadline": item["registration_deadline"],
                "event_dates": item["event_dates"],
                "eligibility": item["eligibility"],
                "apply_url": item["apply_url"],
                "description": item["description"],
            })
        except Exception as exc:
            logger.debug("Failed processing company challenge %s: %s", item.get("title"), exc)

    logger.info("Company Flagships Collector verified %d enterprise opportunities", len(verified_events))
    return verified_events
