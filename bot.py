"""
Operator-Checker Telegram Bot
──────────────────────────────
• Send an MSISDN → get operator + country
• Inline button points to @CYBEREXPERTPK

Designed for Render free-tier (or any host).
"""

import logging, os, requests
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          MessageHandler, ContextTypes, filters)

# ─── CONFIG ────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN")            # set in Render env-vars
REB_URL    = "https://prod-mp.rebtel.com/graphql"
AUTH_HDR   = "application 7443a5f6-01a7-4ce7-8e87-c36212fad4f5"
AUTHOR_URL = "https://t.me/CYBEREXPERTPK"
# ──────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

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

async def start(update: Update, _):
    await update.message.reply_text(
        "👋 *Welcome!*  Send me a number with country code "
        "(e.g. `923001234567`) and I’ll tell you the operator.",
        parse_mode="Markdown",
    )

async def lookup(update: Update, _):
    msisdn = update.message.text.strip()
    if not msisdn.isdigit():
        await update.message.reply_text("❌ Digits only, please.")
        return

    await update.message.reply_text("🔍 Searching…")

    try:
        r = requests.post(
            REB_URL,
            json=gql_body(msisdn),
            headers={
                "Content-Type": "application/json",
                "Authorization": AUTH_HDR,
                "Origin": "https://www.rebtel.com",
                "User-Agent": "OperatorCheckerBot",
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        op = (
            data.get("data", {})
            .get("availability", {})
            .get("operatorLookup", {})
            .get("operators", [{}])[0]
            .get("operator")
        )
        if op:
            reply = (
                f"📡 *Operator* : {op['name']}\n"
                f"🌍 *Country*  : {op['countryId']}"
            )
        else:
            reply = "❌ Invalid or unsupported number."
    except Exception as exc:
        logging.exception("Rebtel call failed: %s", exc)
        reply = "⚠️ Error contacting operator API."

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("👨‍💻 Contact Author", url=AUTHOR_URL)]]
    )
    await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=kb)

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env-var not set in Render.")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
