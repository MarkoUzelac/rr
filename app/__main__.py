"""FastAPI dashboard + background scanner entry point."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from app.engine import MarketEngine
from app.store import Store
from app.telegram_bot import start_telegram

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
store = Store(os.getenv("DATABASE_PATH", "./data/arbitrage.sqlite3"))
engine = MarketEngine(store)

@asynccontextmanager
async def lifespan(app):
    await engine.start()
    bot_task = asyncio.create_task(start_telegram(engine, store))
    try:
        yield
    finally:
        await engine.stop()
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

app = FastAPI(title="Crypto Arbitrage Monitor", version="0.1.0", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text())

@app.get("/api/status")
async def status():
    return JSONResponse(engine.status())

@app.get("/api/opportunities")
async def opportunities():
    return JSONResponse(store.latest_opportunities(100))

@app.get("/api/events")
async def events():
    return JSONResponse(store.latest_events(100))

@app.post("/api/pause")
async def pause():
    engine.paused = True
    return {"paused": True}

@app.post("/api/resume")
async def resume():
    engine.paused = False
    return {"paused": False}

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("APP_HOST", "127.0.0.1"), port=int(os.getenv("APP_PORT", "8080")))
