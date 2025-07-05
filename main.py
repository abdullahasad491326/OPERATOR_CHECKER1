"""
Operator-Checker Telegram Bot  •  Webhook Edition
Runs 24/7 on Render's free Web-Service tier.

• Reads BOT_TOKEN from environment (set in render.yaml)
• FastAPI endpoint = /<token>   (secret path)
• Sets Telegram webhook automatically on startup
• Retries Rebtel API on 409 / 429 / timeouts

Author / contact button → @CYBEREXPERTPK
"""

import os, logging, asyncio, datetime, requests, textwrap
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Config ──────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var not set!")

REB_URL    = "https://prod-mp.rebtel.com/graphql"
AUTH_HDR   = "application 7443a5f6-01a7-4ce7-8e87-c36212fad4f5"
AUTHOR_URL = "https://t.me/CYBEREXPERTPK"
WEBHOOK_PATH = f"/{BOT_TOKEN}"                       # secret

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── Telegram application ───────────────────────────────────
application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = application.bot

async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome!*  Send a number like `923001234567`.", parse_mode="Markdown"
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

async def lookup(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msisdn = update.message.text.strip()
    if not msisdn.isdigit():
        return await update.message.reply_text("❌ Digits only.")
    await update.message.reply_text("🔍 Searching…")

    for attempt in range(3):
        try:
            r = requests.post(
                REB_URL,
                json=gql_body(msisdn),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": AUTH_HDR,
                    "Origin": "https://www.rebtel.com",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Timestamp": datetime.datetime.utcnow()
                        .isoformat(timespec="milliseconds") + "Z",
                },
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            break
        except requests.exceptions.HTTPError:
            logging.warning(
                "HTTP %s try %d: %s",
                r.status_code, attempt + 1,
                textwrap.shorten(r.text, 120, "…"),
            )
            if r.status_code in (409, 429) and attempt < 2:
                await asyncio.sleep(3 * (attempt + 1))
                continue
            return await update.message.reply_text("⚠️ API error.")
        except Exception as e:
            logging.warning("Net error try %d: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return await update.message.reply_text("⚠️ Network error.")

    op = (
        data.get("data", {})
        .get("availability", {})
        .get("operatorLookup", {})
        .get("operators", [{}])[0]
        .get("operator")
    )
    txt = (
        f"📡 *Operator* : {op['name']}\n🌍 *Country*  : {op['countryId']}"
        if op else "❌ Invalid or unsupported number."
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("👨‍💻 Contact Author", url=AUTHOR_URL)]]
    )
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))

# ── FastAPI server ──────────────────────────────────────────
app = FastAPI()

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def set_webhook():
    public_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(public_url)
    logging.info("Webhook set → %s", public_url)
