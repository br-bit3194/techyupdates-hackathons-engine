# Telegram Community Channel & Bot Configuration Guide
## TechyUpdates Hackathons Engine

This guide walks through configuring your Telegram Bot and connecting it to your TechyUpdates Telegram channel or group for automated daily hackathon drops.

---

## 1. Create a Bot with BotFather
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` to start the bot creation wizard.
3. Choose a descriptive display name (e.g. `TechyUpdates Hackathon Radar Bot`).
4. Choose a username ending in `bot` (e.g. `techy_hackathons_bot`).
5. Copy the generated **HTTP API Token** (e.g. `8731782411:AAE2vh7ipY5pRjvIX9nKQ8aUOR0ZzA_...`).
6. Set this as `TELEGRAM_BOT_TOKEN` in your `.env` and GitHub Secrets.

---

## 2. Add the Bot to Your Channel
1. Go to your target Telegram Channel (e.g., `@techy_jobs_updates` or `@techy_hackathons_updates`).
2. Open **Channel Info** → **Administrators** → **Add Administrator**.
3. Search for your bot username and select it.
4. Grant the following permissions:
   * **Post Messages** (Required)
   * **Send Media / Documents** (Required)
5. Save the administrator settings.

---

## 3. Configure the Channel Identifier
In your `.env` file or GitHub Repository Secrets:
* For public channels, specify the channel username:
  ```bash
  TELEGRAM_COMMUNITY_CHANNEL_ID=@techy_jobs_updates
  ```
* For private channels, use the numeric Chat ID (starting with `-100...`):
  ```bash
  TELEGRAM_COMMUNITY_CHANNEL_ID=-1001234567890
  ```

---

## 4. Test the Integration
Run the test suite or execute the trigger locally:
```bash
python api/trigger.py
```
Upon successful execution, the bot compiles the `.xlsx` workbook in-memory and sends the formatted announcement caption and spreadsheet file directly into the Telegram channel.
