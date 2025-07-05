import os, logging, requests, datetime, asyncio, textwrap
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── config ──────────────────────────────────────────────────
BOT_TOKEN  = "7953026946:AAHr1Ka8CXcJ14StSOR-BC3ngalt9mCSx2M"
REB_URL    = "https://prod-mp.rebtel.com/graphql"
AUTH_HDR   = "application 7443a5f6-01a7-4ce7-8e87-c36212fad4f5"
AUTHOR_URL = "https://t.me/CYBEREXPERTPK"
WEBHOOK_PATH = f"/{BOT_TOKEN}"        # secret path
# ────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app  = FastAPI()
tapp = ApplicationBuilder().token(BOT_TOKEN).build()   # telegram application
bot  = tapp.bot

# ── telegram handlers ───────────────────────────────────────
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome!*  Send MSISDN like `923001234567`.",
        parse_mode="Markdown",
    )

async def lookup(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msisdn = update.message.text.strip()
    if not msisdn.isdigit():
        await update.message.reply_text("❌ Digits only.")
        return
    await update.message.reply_text("🔍 Searching…")

    for attempt in range(3):
        try:
            r = requests.post(
                REB_URL,
                json={
                    "variables": {"input": {"msisdns": msisdn}},
                    "operationName": "OperatorLookup",
                    "query": (
                        "mutation OperatorLookup($input: OperatorLookupInput!) {"
                        " availability { operatorLookup(input: $input) {"
                        "  operators { operator { name countryId logoUrl } } } } }"
                    ),
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": AUTH_HDR,
                    "Origin": "https://www.rebtel.com",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Timestamp": datetime.datetime.utcnow()
                        .isoformat(timespec="milliseconds")+"Z",
                },
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            logging.warning("API error (%s) attempt %d", e, attempt+1)
            if attempt < 2:
                await asyncio.sleep(2*(attempt+1))
                continue
            await update.message.reply_text("⚠️ API error.")
            return

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

tapp.add_handler(CommandHandler("start", start))
tapp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))

# ── FastAPI route for Telegram ───────────────────────────────
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await tapp.process_update(update)
    return {"ok": True}

# ── Set the webhook on startup ──────────────────────────────
@app.on_event("startup")
async def set_hook():
    public_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}{WEBHOOK_PATH}"
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(public_url)
    logging.info("Webhook set to %s", public_url)
