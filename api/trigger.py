"""Orchestration Engine & Serverless Entrypoint for TechyUpdates Hackathons."""

import io
import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, List
import httpx
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from services.collectors.devpost import fetch_devpost_hackathons
from services.collectors.unstop import fetch_unstop_hackathons
from services.collectors.mlh_devfolio import fetch_mlh_devfolio_hackathons
from services.collectors.kaggle_dorahacks import fetch_kaggle_dorahacks_challenges
from services.collectors.hack2skill import fetch_hack2skill_hackathons
from services.collectors.liveness_verifier import (
    generate_dedup_hash,
    is_scam_or_blacklisted,
    verify_hackathons_liveness,
)
from services.ai_extractor import extract_and_tier_hackathons, HackathonRecord
from services.excel_builder import build_excel_workbook
from services.telegram_notifier import dispatch_telegram_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("techyupdates.pipeline")


async def run_pipeline() -> Dict[str, Any]:
    """Execute the end-to-end TechyUpdates Hackathons ingestion and broadcast pipeline."""
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 80)
    logger.info("🚀 [TECHYUPDATES HACKATHONS RADAR] Starting Autonomous Pipeline @ %s", start_time.isoformat())
    logger.info("=" * 80)

    # -------------------------------------------------------------------------
    # PHASE 1: Concurrent Ingestion
    # -------------------------------------------------------------------------
    t_phase1 = datetime.now(timezone.utc)
    logger.info("[PHASE 1/5: INGESTION] Launching 5 asynchronous platform collectors...")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        devpost_task = asyncio.create_task(fetch_devpost_hackathons(client))
        unstop_task = asyncio.create_task(fetch_unstop_hackathons(client))
        mlh_devfolio_task = asyncio.create_task(fetch_mlh_devfolio_hackathons(client))
        kaggle_dorahacks_task = asyncio.create_task(fetch_kaggle_dorahacks_challenges(client))
        hack2skill_task = asyncio.create_task(fetch_hack2skill_hackathons(client))

        results = await asyncio.gather(
            devpost_task,
            unstop_task,
            mlh_devfolio_task,
            kaggle_dorahacks_task,
            hack2skill_task,
            return_exceptions=True,
        )

    all_raw: List[Dict[str, Any]] = []
    collector_names = ["Devpost", "Unstop", "MLH & Devfolio", "Kaggle & DoraHacks", "Hack2skill"]
    for name, res in zip(collector_names, results):
        if isinstance(res, list):
            logger.info("  ✓ %s Collector: %d opportunities ingested", name, len(res))
            all_raw.extend(res)
        else:
            logger.error("  ❌ %s Collector failed: %s", name, res)

    elapsed_p1 = (datetime.now(timezone.utc) - t_phase1).total_seconds()
    logger.info("[PHASE 1/5: INGESTION] Completed in %.2fs. Total raw events: %d", elapsed_p1, len(all_raw))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 2: Deduplication & Quality / Scam Filter
    # -------------------------------------------------------------------------
    t_phase2 = datetime.now(timezone.utc)
    logger.info("[PHASE 2/5: DEDUP & FILTER] Filtering spam and deduplicating records...")

    seen_hashes = set()
    filtered_events: List[Dict[str, Any]] = []

    for item in all_raw:
        # Anti-scam filter
        if is_scam_or_blacklisted(item):
            continue

        platform = item.get("platform", "Unknown")
        title = item.get("title", "")
        if not title:
            continue

        h = generate_dedup_hash(platform, title)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        filtered_events.append(item)

    elapsed_p2 = (datetime.now(timezone.utc) - t_phase2).total_seconds()
    logger.info("[PHASE 2/5: DEDUP & FILTER] Completed in %.2fs. Clean unique events: %d (Purged: %d)",
                elapsed_p2, len(filtered_events), len(all_raw) - len(filtered_events))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 3: Liveness & Active Registration Check
    # -------------------------------------------------------------------------
    t_phase3 = datetime.now(timezone.utc)
    logger.info("[PHASE 3/5: LIVENESS] Verifying active registration status...")

    active_events = await verify_hackathons_liveness(filtered_events)
    elapsed_p3 = (datetime.now(timezone.utc) - t_phase3).total_seconds()
    logger.info("[PHASE 3/5: LIVENESS] Completed in %.2fs. Verified active: %d", elapsed_p3, len(active_events))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 4: AI Extraction & Categorization
    # -------------------------------------------------------------------------
    t_phase4 = datetime.now(timezone.utc)
    logger.info("[PHASE 4/5: AI CATEGORIZATION] Processing through Gemini 3 AI cascade...")

    enriched_records: List[HackathonRecord] = await extract_and_tier_hackathons(active_events, batch_size=50)

    category_counts = {
        "AI & GenAI Hackathons": 0,
        "Web3 & Open Source Hackathons": 0,
        "Student & University Hackathons": 0,
        "Open Innovation & Hiring Challenges": 0,
    }
    for r in enriched_records:
        if r.category in category_counts:
            category_counts[r.category] += 1

    elapsed_p4 = (datetime.now(timezone.utc) - t_phase4).total_seconds()
    logger.info("  Distribution Summary:")
    logger.info("    🤖 AI & GenAI Hackathons:       %d", category_counts["AI & GenAI Hackathons"])
    logger.info("    🌐 Web3 & Open Source Grants:    %d", category_counts["Web3 & Open Source Hackathons"])
    logger.info("    🎓 Student & University Hacks:   %d", category_counts["Student & University Hackathons"])
    logger.info("    🏆 Open Innovation & Hiring:     %d", category_counts["Open Innovation & Hiring Challenges"])
    logger.info("[PHASE 4/5: AI CATEGORIZATION] Complete in %.2fs. Total enriched: %d", elapsed_p4, len(enriched_records))
    logger.info("-" * 80)

    # -------------------------------------------------------------------------
    # PHASE 5: In-Memory Excel Build & Telegram Dispatch
    # -------------------------------------------------------------------------
    t_phase5 = datetime.now(timezone.utc)
    logger.info("[PHASE 5/5: WORKBOOK & DISPATCH] Building 4-tab styled spreadsheet in-memory...")

    excel_buffer = build_excel_workbook(enriched_records)
    buffer_size = excel_buffer.getbuffer().nbytes
    logger.info("  ✓ Generated Excel spreadsheet (%d bytes / %.2f KB)", buffer_size, buffer_size / 1024)

    logger.info("  📡 Dispatching to TechyUpdates Telegram community channel...")
    dispatched = await dispatch_telegram_document(excel_buffer, enriched_records)

    local_file_path = None
    if dispatched:
        logger.info("  ✓ Telegram broadcast confirmed successful! Cleaning local temp files...")
        for fname in os.listdir(PROJECT_ROOT):
            if fname.endswith(".xlsx") and "Hackathons" in fname:
                try:
                    fpath = os.path.join(PROJECT_ROOT, fname)
                    os.remove(fpath)
                    logger.info("    - Removed local temp file: %s", fname)
                except Exception as exc:
                    logger.debug("    - Could not remove %s: %s", fname, exc)
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        local_filename = f"TechyUpdates_Hackathons_{date_str}.xlsx"
        local_file_path = os.path.join(PROJECT_ROOT, local_filename)
        try:
            excel_buffer.seek(0)
            with open(local_file_path, "wb") as f:
                f.write(excel_buffer.getvalue())
            logger.info("  💾 Local Excel backup saved: %s", local_file_path)
        except Exception as exc:
            logger.error("  ❌ Could not write local Excel backup: %s", exc, exc_info=True)
            local_file_path = None

    elapsed_p5 = (datetime.now(timezone.utc) - t_phase5).total_seconds()
    total_elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info("[PHASE 5/5: WORKBOOK & DISPATCH] Complete in %.2fs", elapsed_p5)
    logger.info("=" * 80)
    logger.info("✨ [PIPELINE FINISHED] Execution completed in %.2fs (%.1f mins)", total_elapsed, total_elapsed / 60)
    logger.info("Summary: %d raw → %d deduped → %d live active → %d enriched → Telegram: %s",
                len(all_raw), len(filtered_events), len(active_events), len(enriched_records), dispatched)
    logger.info("=" * 80)

    result_payload = {
        "status": "success",
        "service": "techyupdates-hackathons-engine",
        "timestamp": start_time.isoformat(),
        "elapsed_seconds": round(total_elapsed, 2),
        "total_raw": len(all_raw),
        "total_deduped": len(filtered_events),
        "total_active_live": len(active_events),
        "category_distribution": category_counts,
        "telegram_dispatched": dispatched,
    }
    if local_file_path:
        result_payload["local_file_saved"] = local_file_path

    return result_payload


def authenticate_request(headers: Dict[str, str], query_params: Dict[str, List[str]] = None) -> bool:
    """Verify credentials against CRON_SECRET or vercel-cron user-agent."""
    expected_secret = os.getenv("CRON_SECRET")
    if not expected_secret:
        logger.info("[AUTH] CRON_SECRET environment variable not set. Permitting request in dev mode.")
        return True

    # 1. Bearer token in Authorization header
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if auth_header:
        parts = auth_header.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected_secret:
            logger.info("[AUTH] Request authorized via Bearer token.")
            return True

    # 2. Query param ?secret=<secret> or ?key=<secret>
    if query_params:
        provided_key = (query_params.get("secret") or query_params.get("key") or [None])[0]
        if provided_key == expected_secret:
            logger.info("[AUTH] Request authorized via URL secret parameter.")
            return True

    # 3. Vercel cron caller
    user_agent = headers.get("User-Agent") or headers.get("user-agent") or ""
    if "vercel-cron" in user_agent.lower():
        logger.info("[AUTH] Request authorized via vercel-cron caller.")
        return True

    logger.warning("[AUTH] Unauthorized request: missing or invalid credentials.")
    return False


class handler(BaseHTTPRequestHandler):
    """Vercel Python Serverless HTTP Request Handler."""

    def _send_response_json(self, status_code: int, data: Dict[str, Any]):
        response_bytes = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        """Handle Vercel Cron GET invocation or health check."""
        parsed_url = urlparse(self.path)
        parsed_path = parsed_url.path.rstrip("/")
        query_params = parse_qs(parsed_url.query)

        logger.info("[HTTP] GET request received for path: %s", self.path)

        if parsed_path in ("/api/health", "/health", ""):
            self._send_response_json(200, {
                "status": "healthy",
                "service": "techyupdates-hackathons-engine",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        headers_dict = {k: v for k, v in self.headers.items()}
        if not authenticate_request(headers_dict, query_params):
            self._send_response_json(401, {
                "error": "Unauthorized: Invalid or missing Bearer token",
                "hint": "Provide Authorization: Bearer <CRON_SECRET> header or ?key=<CRON_SECRET> query parameter."
            })
            return

        try:
            result = asyncio.run(run_pipeline())
            self._send_response_json(200, result)
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            self._send_response_json(500, {"error": "Pipeline execution failed", "details": str(exc)})

    def do_POST(self):
        """Handle manual webhook POST trigger."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        logger.info("[HTTP] POST request received for path: %s", self.path)

        headers_dict = {k: v for k, v in self.headers.items()}
        if not authenticate_request(headers_dict, query_params):
            self._send_response_json(401, {
                "error": "Unauthorized: Invalid or missing Bearer token",
                "hint": "Provide Authorization: Bearer <CRON_SECRET> header or ?key=<CRON_SECRET> query parameter."
            })
            return

        try:
            result = asyncio.run(run_pipeline())
            self._send_response_json(200, result)
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            self._send_response_json(500, {"error": "Pipeline execution failed", "details": str(exc)})


if __name__ == "__main__":
    # Direct CLI execution
    logger.info("Executing TechyUpdates Hackathons Pipeline directly via CLI...")
    result = asyncio.run(run_pipeline())
    print("\n--- Pipeline Result ---")
    print(json.dumps(result, indent=2))
