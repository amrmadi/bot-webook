import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import logging
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_application = None

def get_app():
    global _application
    if _application is None:
        logger.info("Building application...")
        from bot import build_application
        from database import init_db

        async def vercel_post_init(app):
            init_db()
            logger.info("Database initialized (no background checker)")

        _application = build_application(post_init_fn=vercel_post_init)
    return _application

@app.route("/api/webhook", methods=["POST"])
def webhook():
    from telegram import Update

    application = get_app()
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))

    return "OK", 200

@app.route("/api/cron", methods=["GET"])
def cron():
    from bot import check_new_events
    from database import init_db

    init_db()
    application = get_app()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_new_events(application))
    return "Checked", 200

@app.route("/api/set_webhook", methods=["GET"])
def set_webhook():
    url = request.args.get("url")
    if not url:
        return "Missing ?url=", 400

    application = get_app()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.bot.set_webhook(url=f"{url}/api/webhook"))
    return f"Webhook set to {url}/api/webhook", 200

@app.route("/api")
def index():
    return "webook bot is running", 200
