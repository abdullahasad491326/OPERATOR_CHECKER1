"""
Operator-Checker Telegram Bot
─────────────────────────────
Runs 24/7 on Render Background Worker (free).

• Users send an MSISDN → bot replies with operator + country
• Rebtel API request with retry/back-off
• drop_pending_updates handles the daily Render restart

⚠️  Your bot token is hard-coded; keep this repo private.
"""

import asyncio, datetime, logging, textwrap, requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── CONFIG ──────────────────────────────────────────────────────────
BOT_TOKEN  = "7953026946:AAHr1Ka8CXcJ14StSOR-BC3ngalt9mCSx2M"    # ← your live token
REB_URL    = "https://prod-mp.rebtel.com/graphql"
AUTH_HDR   = "application 7443a5f6-01a7-4ce7-8e87-c36212fad4f5"
AUTHOR_URL = "https://t.me/CYBEREXPERTPK"
# ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def gql_body(msisdn: str) -> dict:
    return {
        "variables": {"input": {"msisdns": msisdn}},
        "operationName": "OperatorLookup",
        "query": (
            "mutation OperatorLookup($input: OperatorLookupInput!) {"
            " availability { operatorLookup(input: $input) {"
            "  operators { operator { name countryId logoUrl } } } } }"
        ),
    }

async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome!*  Send a mobile number with country-code "
        "(e.g. `923001234567`) and I’ll tell you the operator.",
        parse_mode="Markdown",
    )

async def lookup(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msisdn = update.message.text.strip()
    if not msisdn.isdigit():
        await update.message.reply_text("❌ Digits only, please.")
        return

    await update.message.reply_text("🔍 Searching…")

    # ── Robust request with retry/back-off ───────────────────────────
    for attempt in range(3):              # 3 tries
        try:
            resp = requests.post(
                REB_URL,
                json=gql_body(msisdn),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": AUTH_HDR,
                    "Origin": "https://www.rebtel.com",
                    "User-Agent": "OperatorCheckerBot",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Timestamp": datetime.datetime.utcnow()
                        .isoformat(timespec="milliseconds") + "Z",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "en",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            break                                   # success
        except requests.exceptions.HTTPError:
            logging.warning(
                "HTTP %s on attempt %d: %s",
                resp.status_code, attempt + 1,
                textwrap.shorten(resp.text, width=120, placeholder="…"),
            )
            if resp.status_code in (409, 429) and attempt < 2:
                await asyncio.sleep(3 * (attempt + 1))  # 3s, 6s
                continue
            raise
        except Exception as e:
            logging.warning("Network error (try %d): %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))  # 2s, 4s
                continue
            raise

    try:
        op = (
            data.get("data", {})
            .get("availability", {})
            .get("operatorLookup", {})
            .get("operators", [{}])[0]
            .get("operator")
        )
        reply = (
            f"📡 *Operator* : {op['name']}\n"
            f"🌍 *Country*  : {op['countryId']}"
        ) if op else "❌ Invalid or unsupported number."
    except Exception as exc:
        logging.exception("Parsing failed: %s", exc)
        reply = "⚠️ Unexpected API response."

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("👨‍💻 Contact Author", url=AUTHOR_URL)]]
    )
    await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=kb)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))

    # free worker restarts daily → drop old updates
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
