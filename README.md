# TechyUpdates Hackathons Engine
## Autonomous Global Hackathon & Competition Radar for Developers

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Daily Pipeline](https://github.com/br-bit3194/techyupdates-hackathons-engine/actions/workflows/daily_pipeline.yml/badge.svg)](https://github.com/br-bit3194/techyupdates-hackathons-engine/actions)

An autonomous data pipeline and AI categorization engine that scours the global tech and student ecosystem daily for verified hackathons, coding competitions, open-source grants, and corporate hiring challenges.

Enriched using **Google Gemini 3 AI**, the engine compiles an enterprise-grade 4-tab Excel workbook (`.xlsx`) in-memory and broadcasts daily opportunity drops directly to your **Telegram channel** (`@techy_hackathons_updates`).

---

## 🌟 Key Features

* **Multi-Source Asynchronous Ingestion:** High-speed parallel scraping across Devpost, Unstop, Hack2skill, Devfolio, MLH, Kaggle, DoraHacks, and HackerEarth.
* **Strict Registration Deadline Verification:** Only open, active opportunities with future deadlines are retained. Expired and past challenges are purged automatically.
* **AI Extraction & Domain Categorization:** Powered by Google Gemini (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.8-flash`) with instant heuristic rule failovers.
* **Anti-Scam & Quality Filter:** MD5 deduplication and blacklist heuristics purge fake paid contests, spam MLM tokens, and dubious fee-charging certificate schemes.
* **In-Memory Excel Generation:** Compiles 4 styled, color-coded tabs with auto-filters, frozen headers, and 1-click clickable registration hyperlinks (`openpyxl`).
* **Automated Telegram Channel Broadcast:** Humanized summary captions and direct document delivery to Telegram channels via Bot API.
* **Zero Server Infrastructure:** Runs on GitHub Actions automated daily cron (`02:30 UTC / 8:00 AM IST`) and Vercel Python serverless functions.

---

## 📊 4 Categorized Excel Tabs

| Sheet Tab Name | Focus Area | Color Theme |
|:---|:---|:---:|
| **🤖 AI & GenAI Hackathons** | Generative AI, Autonomous Agents, LLMs, Computer Vision, Kaggle ML | Electric Indigo (`#4338CA`) |
| **🌐 Web3 & Open Source** | Smart Contracts, Blockchain, DoraHacks Grants, Public Goods | Deep Teal (`#0F766E`) |
| **🎓 Student & University** | MLH Collegiate Season, Devfolio University Hacks, Beginner-friendly | Emerald Forest (`#065F46`) |
| **🏆 Open Innovation & Hiring** | Corporate Sprints, Unstop Challenges, Cash Prize Tournaments | Deep Wine Red (`#991B1B`) |

---

## 🛠️ Quick Start

### 1. Clone & Setup Environment
```bash
git clone https://github.com/br-bit3194/techyupdates-hackathons-engine.git
cd techyupdates-hackathons-engine

# Create & activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
Key variables:
* `GEMINI_API_KEY`: Google AI Studio API Key.
* `TELEGRAM_BOT_TOKEN`: Bot token from `@BotFather`.
* `TELEGRAM_COMMUNITY_CHANNEL_ID`: Destination Telegram channel (e.g. `@techy_hackathons_updates`).

### 3. Run Pipeline Locally
```bash
python api/trigger.py
```

### 4. Run Test Suite
```bash
pytest tests/ -v
```

---

## 📄 License
Distributed under the MIT License. Built with ❤️ for developers and builders.
