"""Telegram control and alert bot. Read-only; no order placement."""
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

async def start_telegram(engine, store):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        while True:
            await asyncio.sleep(3600)
    bot = Bot(token=token)
    dp = Dispatcher()
    allowed = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    def authorized(message: Message):
        return bool(allowed) and message.from_user and str(message.from_user.id) == allowed

    @dp.message(Command("start", "help"))
    async def help_cmd(message: Message):
        if authorized(message):
            await message.answer("Crypto Arbitrage Monitor\n/status — status\n/opps — latest candidates\n/pause — pause\n/resume — resume\nPAPER mode only; no real orders.")

    @dp.message(Command("status"))
    async def status_cmd(message: Message):
        if not authorized(message): return
        s = engine.status()
        await message.answer(f"Mode: {s['mode']}\nExchanges: {', '.join(s['exchanges']) or 'none'}\nPairs: {', '.join(s['symbols'])}\nScans: {s['scan_count']}\nCandidates: {s['opportunity_count']}\nPaused: {s['paused']}\nError: {s['last_error'] or 'none'}")

    @dp.message(Command("opps"))
    async def opps_cmd(message: Message):
        if not authorized(message): return
        rows = store.latest_opportunities(5)
        if not rows:
            await message.answer("No recorded opportunities.")
        else:
            await message.answer("\n".join(f"{r['symbol']} {r['buy_exchange']} → {r['sell_exchange']} | est. net {r['net_pct']}% | {r['estimated_net_quote']} quote" for r in rows))

    @dp.message(Command("pause"))
    async def pause_cmd(message: Message):
        if authorized(message):
            engine.paused = True
            await message.answer("Scanner paused.")

    @dp.message(Command("resume"))
    async def resume_cmd(message: Message):
        if authorized(message):
            engine.paused = False
            await message.answer("Scanner resumed.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
