"""TechyUpdates Hackathons Configuration: Platform endpoints, feed URLs, target queries, and filters."""

from typing import Dict, List, Set

# Platform Search Feeds & Endpoints
DEVPOST_CONFIG = {
    "base_url": "https://devpost.com/api/hackathons",
    "search_urls": [
        "https://devpost.com/hackathons?challenge_type[]=online&status[]=upcoming&status[]=open&sort_by=recently-added",
        "https://devpost.com/hackathons?challenge_type[]=in-person&status[]=upcoming&status[]=open&sort_by=recently-added",
        "https://devpost.com/hackathons?themes[]=AI%20%2F%20Machine%20Learning&status[]=open",
        "https://devpost.com/hackathons?themes[]=Blockchain&status[]=open",
    ]
}

UNSTOP_CONFIG = {
    "api_url": "https://unstop.com/api/public/opportunity/search-result",
    "categories": ["hackathons", "coding-challenges", "quizzes", "hiring-challenges"],
}

DEVFOLIO_CONFIG = {
    "api_url": "https://api.devfolio.co/api/hackathons",
    "filter": "upcoming,open_now",
}

MLH_CONFIG = {
    "seasons": ["2026", "2025"],
    "base_url": "https://mlh.io/seasons/2026/events",
}

DORAHACKS_CONFIG = {
    "api_url": "https://dorahacks.io/api/hackathons",
}

KAGGLE_CONFIG = {
    "api_url": "https://www.kaggle.com/api/v1/competitions/list",
    "rss_url": "https://www.kaggle.com/feeds/competitions.xml",
}

HACKEREARTH_CONFIG = {
    "api_url": "https://www.hackerearth.com/challenges/api/upcoming_and_ongoing_challenges/",
}

HACK2SKILL_CONFIG = {
    "base_url": "https://hack2skill.com/hackathons",
    "api_url": "https://api.hack2skill.com/api/v1/hackathons",
}

# Positive keywords for hackathon & competition validation
TECH_HACKATHON_KEYWORDS: Set[str] = {
    "hackathon",
    "hack",
    "buildathon",
    "ideathon",
    "codeathon",
    "coding challenge",
    "coding contest",
    "bounty",
    "grant",
    "data science competition",
    "machine learning challenge",
    "ai challenge",
    "genai",
    "llm",
    "web3",
    "defi",
    "blockchain",
    "open source",
    "developer sprint",
    "hiring challenge",
    "innovation challenge",
    "campus hackathon",
    "collegiate",
    "fellowship hack",
}

# Anti-scam heuristic blacklist (purges pay-for-certificate schemes, MLM token spam, dubious upfront fees)
SCAM_BLACKLIST_KEYWORDS: List[str] = [
    "guaranteed 100x token",
    "crypto pump",
    "pay for certificate only",
    "mandatory registration fee of 5000",
    "multi-level marketing",
    "pyramid scheme",
    "send eth to receive prize",
    "private key submission",
    "seed phrase required",
    "whatsapp only registration",
    "telegram payment required",
]

# Per-request timeout in seconds
REQUEST_TIMEOUT_SECONDS: float = 8.0
