"""Cross-exchange BTC spread scanner. Paper-only by design."""
import asyncio
import logging
import os
import time
from typing import Any

import ccxt.async_support as ccxt

log = logging.getLogger("arb.engine")

class MarketEngine:
    def __init__(self, store):
        self.store = store
        self.exchange_ids = [x.strip() for x in os.getenv("EXCHANGES", "kucoin,kraken,coinbase").split(",") if x.strip()]
        self.symbols = [x.strip() for x in os.getenv("SYMBOLS", "BTC/USDT").split(",") if x.strip()]
        self.min_edge = float(os.getenv("MIN_NET_EDGE_PCT", "0.35")) / 100
        self.slippage = float(os.getenv("SLIPPAGE_BUFFER_PCT", "0.20")) / 100
        self.fee = float(os.getenv("ESTIMATED_TAKER_FEE_PCT", "0.10")) / 100
        self.quote_size = float(os.getenv("ORDER_SIZE_QUOTE", "25"))
        self.interval = max(2, int(os.getenv("SCAN_INTERVAL_SECONDS", "5")))
        self.exchanges: dict[str, Any] = {}
        self.paused = False
        self.running = False
        self.last_scan = None
        self.last_error = None
        self.scan_count = 0
        self.opportunity_count = 0
        self.started = time.time()

    async def start(self):
        self.running = True
        for exchange_id in self.exchange_ids:
            try:
                cls = getattr(ccxt, exchange_id)
                ex = cls({"enableRateLimit": True, "timeout": 12000})
                await ex.load_markets()
                self.exchanges[exchange_id] = ex
                self.store.event("INFO", f"Loaded public markets: {exchange_id}")
            except Exception as exc:
                self.last_error = f"{exchange_id}: {exc}"
                self.store.event("ERROR", "Exchange initialization failed", {"exchange": exchange_id, "error": str(exc)})
        asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        for ex in self.exchanges.values():
            try:
                await ex.close()
            except Exception:
                pass

    async def _loop(self):
        while self.running:
            started = time.monotonic()
            if not self.paused:
                try:
                    await self.scan_once()
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                    log.exception("scan failed")
                    self.store.event("ERROR", "Scan failed", {"error": str(exc)})
            await asyncio.sleep(max(0.1, self.interval - (time.monotonic() - started)))

    async def scan_once(self):
        books = {}
        for exchange_id, ex in self.exchanges.items():
            for symbol in self.symbols:
                if symbol not in ex.markets or not ex.markets[symbol].get("active", True):
                    continue
                try:
                    ob = await ex.fetch_order_book(symbol, limit=5)
                    if ob.get("asks") and ob.get("bids"):
                        books[(exchange_id, symbol)] = {
                            "ask": float(ob["asks"][0][0]), "ask_qty": float(ob["asks"][0][1]),
                            "bid": float(ob["bids"][0][0]), "bid_qty": float(ob["bids"][0][1]),
                        }
                except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as exc:
                    self.store.event("WARN", "Transient market data error", {"exchange": exchange_id, "symbol": symbol, "error": str(exc)})
                except ccxt.BaseError as exc:
                    self.store.event("WARN", "Exchange rejected market data request", {"exchange": exchange_id, "symbol": symbol, "error": str(exc)})
        now = time.time()
        self.last_scan = now
        self.scan_count += 1
        for symbol in self.symbols:
            venues = [(eid, b) for (eid, sym), b in books.items() if sym == symbol]
            for buy_id, buy in venues:
                for sell_id, sell in venues:
                    if buy_id == sell_id or buy["ask"] <= 0:
                        continue
                    base_qty = self.quote_size / buy["ask"]
                    if base_qty > min(buy["ask_qty"], sell["bid_qty"]):
                        continue
                    gross = (sell["bid"] - buy["ask"]) / buy["ask"]
                    net = gross - (2 * self.fee) - self.slippage
                    if net <= 0:
                        continue
                    row = {
                        "symbol": symbol, "buy_exchange": buy_id, "sell_exchange": sell_id,
                        "buy_ask": buy["ask"], "sell_bid": sell["bid"],
                        "gross_pct": round(gross * 100, 5), "net_pct": round(net * 100, 5),
                        "quote_size": self.quote_size, "estimated_net_quote": round(self.quote_size * net, 6),
                        "mode": "PAPER", "timestamp": now
                    }
                    self.opportunity_count += 1
                    self.store.opportunity(row)
                    if net >= self.min_edge:
                        self.store.event("OPPORTUNITY", "Paper opportunity after estimated fees and slippage", row)

    def status(self):
        return {
            "mode": "PAPER", "live_trading": False, "paused": self.paused,
            "exchanges": list(self.exchanges.keys()), "symbols": self.symbols,
            "last_scan": self.last_scan, "last_error": self.last_error,
            "scan_count": self.scan_count, "opportunity_count": self.opportunity_count,
            "uptime_seconds": int(time.time() - self.started),
            "min_net_edge_pct": self.min_edge * 100, "order_size_quote": self.quote_size
        }
