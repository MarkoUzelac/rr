"""Cross-exchange scanner using order-book depth. PAPER-only."""
import asyncio
import logging
import os
import time
from typing import Any

import ccxt.async_support as ccxt

log = logging.getLogger("arb.engine")


def _consume(levels, target_qty):
    """Return VWAP and filled base quantity by walking an order-book side."""
    remaining = target_qty
    quote_total = 0.0
    filled = 0.0
    for price, amount in levels:
        price, amount = float(price), float(amount)
        if price <= 0 or amount <= 0:
            continue
        take = min(remaining, amount)
        quote_total += take * price
        filled += take
        remaining -= take
        if remaining <= 1e-12:
            break
    if remaining > 1e-12 or filled <= 0:
        return None
    return quote_total / filled, filled


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
        self.max_book_age_ms = max(1000, int(os.getenv("MAX_BOOK_AGE_MS", "10000")))
        self.exchanges: dict[str, Any] = {}
        self.paused = False
        self.running = False
        self.last_scan = None
        self.last_error = None
        self.scan_count = 0
        self.opportunity_count = 0
        self.started = time.time()
        self._loop_task = None

    async def start(self):
        if self.running:
            return
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
        self._loop_task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for ex in self.exchanges.values():
            try:
                await ex.close()
            except Exception:
                log.exception("exchange close failed")
        self.exchanges.clear()

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
                    ob = await ex.fetch_order_book(symbol, limit=20)
                    timestamp = ob.get("timestamp")
                    age_ms = max(0, int(time.time() * 1000 - timestamp)) if timestamp else None
                    if age_ms is not None and age_ms > self.max_book_age_ms:
                        self.store.event("WARN", "Discarded stale order book", {"exchange": exchange_id, "symbol": symbol, "age_ms": age_ms})
                        continue
                    if ob.get("asks") and ob.get("bids"):
                        books[(exchange_id, symbol)] = {"asks": ob["asks"], "bids": ob["bids"], "age_ms": age_ms}
                except ccxt.BaseError as exc:
                    self.store.event("WARN", "Market data request failed", {"exchange": exchange_id, "symbol": symbol, "error": str(exc)})
        now = time.time()
        self.last_scan = now
        self.scan_count += 1

        for symbol in self.symbols:
            venues = [(eid, book) for (eid, sym), book in books.items() if sym == symbol]
            for buy_id, buy in venues:
                for sell_id, sell in venues:
                    if buy_id == sell_id:
                        continue
                    best_ask = float(buy["asks"][0][0])
                    if best_ask <= 0:
                        continue
                    target_qty = self.quote_size / best_ask
                    buy_fill = _consume(buy["asks"], target_qty)
                    sell_fill = _consume(sell["bids"], target_qty)
                    if not buy_fill or not sell_fill:
                        continue
                    buy_vwap, filled_qty = buy_fill
                    sell_vwap, _ = sell_fill
                    buy_cost = buy_vwap * filled_qty
                    sell_value = sell_vwap * filled_qty
                    gross_quote = sell_value - buy_cost
                    gross = gross_quote / buy_cost if buy_cost else 0
                    fees_quote = (buy_cost + sell_value) * self.fee
                    slippage_quote = (buy_cost + sell_value) * self.slippage / 2
                    net_quote = gross_quote - fees_quote - slippage_quote
                    net = net_quote / buy_cost if buy_cost else 0
                    if net < self.min_edge:
                        continue
                    row = {
                        "symbol": symbol, "buy_exchange": buy_id, "sell_exchange": sell_id,
                        "buy_vwap": round(buy_vwap, 10), "sell_vwap": round(sell_vwap, 10),
                        "base_qty": round(filled_qty, 12), "gross_pct": round(gross * 100, 6),
                        "net_pct": round(net * 100, 6), "quote_size": round(buy_cost, 8),
                        "estimated_net_quote": round(net_quote, 8), "mode": "PAPER",
                        "buy_book_age_ms": buy["age_ms"], "sell_book_age_ms": sell["age_ms"],
                        "timestamp": now,
                    }
                    self.opportunity_count += 1
                    self.store.opportunity(row)
                    self.store.event("OPPORTUNITY", "Paper candidate passed net edge and visible depth", row)

    def status(self):
        return {
            "mode": "PAPER", "live_trading": False, "paused": self.paused,
            "exchanges": list(self.exchanges.keys()), "symbols": self.symbols,
            "last_scan": self.last_scan, "last_error": self.last_error,
            "scan_count": self.scan_count, "opportunity_count": self.opportunity_count,
            "uptime_seconds": int(time.time() - self.started),
            "min_net_edge_pct": self.min_edge * 100, "order_size_quote": self.quote_size,
        }
