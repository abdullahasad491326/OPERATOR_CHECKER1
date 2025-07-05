"""
Operator-Checker Telegram Bot
─────────────────────────────
• Send MSISDN → get operator + country
• Compatible with python-telegram-bot 21.1.x
• drop_pending_updates handled in run_polling()

Author / Contact button → @CYBEREXPERTPK
"""

import logging
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─── CONFIG ───────────────────────────────────────────────────
BOT_TOKEN = "7953026946:AAHr1Ka8CXcJ14StSOR-BC3ngalt9mCSx2M"
REB_URL   = "https://prod-mp.rebtel.com/graphql"
AUTH_HDR  = "application 7443a5f6-01a7-4ce7-8e87-c36212fad4f5"
AUTHOR_URL = "https://t.me/CYBEREXPERTPK"
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def gql_body(msisdn: str) -> dict:
    """Rebtel GraphQL payload."""
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
        "👋 *Welcome!*  Send a mobile number with country code "
        "(e.g. `923001234567`) and I’ll tell you the operator.",
        parse_mode="Markdown",
    )

async def lookup(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msisdn = update.message.text.strip()
    if not msisdn.isdigit():
        await update.message.reply_text("❌ Digits only, please.")
        return

    await update.message.reply_text("🔍 Searching…")

    try:
        resp = requests.post(
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
        resp.raise_for_status()
        data = resp.json()

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
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))

    # drop pending updates to avoid 409 Conflict on redeploy
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
