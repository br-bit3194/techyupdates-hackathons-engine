"""Telegram Community Broadcaster for TechyUpdates Hackathons."""

import io
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict
import httpx
from services.ai_extractor import HackathonRecord

logger = logging.getLogger("techyupdates.telegram_notifier")


def generate_telegram_caption(records: List[HackathonRecord]) -> str:
    """Format humanized community broadcast message for Telegram (guaranteed < 1024 chars)."""
    now_utc = datetime.now(timezone.utc)
    date_formatted = now_utc.strftime("%d %b %Y")

    category_counts: Dict[str, int] = {
        "AI & GenAI Hackathons": 0,
        "Web3 & Open Source Hackathons": 0,
        "Student & University Hackathons": 0,
        "Open Innovation & Hiring Challenges": 0,
    }

    for r in records:
        if r.category in category_counts:
            category_counts[r.category] += 1

    total_count = len(records)

    # Curate crisp 1-line highlights across each category
    highlights: List[str] = []
    for cat_name, icon in [
        ("AI & GenAI Hackathons", "🤖"),
        ("Student & University Hackathons", "🎓"),
        ("Open Innovation & Hiring Challenges", "🏆"),
        ("Web3 & Open Source Hackathons", "🌐"),
    ]:
        matching = [r for r in records if r.category == cat_name]
        if matching:
            top = matching[0]
            # Compact platform & title
            clean_title = top.title[:35].strip() + ("..." if len(top.title) > 35 else "")
            clean_platform = top.platform.split("(")[0].strip()
            prize_str = f" • {top.prize_pool[:18]}" if top.prize_pool and "unspecified" not in top.prize_pool.lower() else ""
            highlights.append(f"• {icon} *{clean_platform}* — {clean_title}{prize_str}")

    featured_block = "\n".join(highlights[:4]) if highlights else "• 🚀 Explore top active hackathons & challenges in the attached file!"

    caption = (
        f"🚀 *Hey Tech Fam! Here is your daily TechyUpdates Hackathons Radar!* 🏆\n\n"
        f"📅 *Date:* {date_formatted}\n"
        f"✨ We scoured and verified *{total_count} active hackathons & coding challenges* with open registrations!\n\n"
        f"🎯 *What's inside today's drop:*\n"
        f"  🤖 *AI & GenAI Hackathons:* {category_counts['AI & GenAI Hackathons']}\n"
        f"  🌐 *Web3 & Open Source Grants:* {category_counts['Web3 & Open Source Hackathons']}\n"
        f"  🎓 *Student & University Hackathons:* {category_counts['Student & University Hackathons']}\n"
        f"  🏆 *Open Innovation & Hiring Sprints:* {category_counts['Open Innovation & Hiring Challenges']}\n\n"
        f"🔥 *Top Featured Challenges:*\n"
        f"{featured_block}\n\n"
        f"📂 *Attached Excel file:* 4 categorized tabs with 1-click registration links & deadline alerts.\n"
        f"💡 *Pro-tip:* Form your squad early & register before deadlines close! Best of luck building! 🌟"
    )

    # Hard safety guard for Telegram 1024-char caption limit
    if len(caption) > 1000:
        caption = caption[:990].rstrip() + "\n...\n📂 *Attached Excel:* 4 categorized tabs."

    return caption


async def dispatch_telegram_document(excel_buffer: io.BytesIO, records: List[HackathonRecord]) -> bool:
    """Send generated .xlsx workbook with executive caption to the Telegram channel."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_COMMUNITY_CHANNEL_ID")

    if not bot_token or not channel_id:
        logger.warning(
            "[TELEGRAM] TELEGRAM_BOT_TOKEN or TELEGRAM_COMMUNITY_CHANNEL_ID not set. "
            "Skipping community broadcast."
        )
        return False

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"TechyUpdates_Hackathons_{date_str}.xlsx"
    caption_text = generate_telegram_caption(records)

    excel_buffer.seek(0)
    file_bytes = excel_buffer.getvalue()

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "document": (filename, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            }
            data = {
                "chat_id": channel_id,
                "caption": caption_text,
                "parse_mode": "Markdown",
            }
            response = await client.post(telegram_url, data=data, files=files)
            if response.status_code == 200:
                logger.info("  ✓ Successfully broadcasted %s to Telegram channel %s", filename, channel_id)
                return True
            else:
                logger.error(
                    "  ❌ Telegram API returned error code %d: %s",
                    response.status_code,
                    response.text,
                )
                return False
    except Exception as exc:
        logger.exception("  ❌ Failed dispatching document to Telegram: %s", exc)
        return False
