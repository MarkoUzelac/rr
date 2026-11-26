"""SQLite event ledger for market observations and PAPER fills."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class Store:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS opportunities(
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              symbol TEXT NOT NULL, buy_exchange TEXT NOT NULL, sell_exchange TEXT NOT NULL,
              buy_ask REAL NOT NULL, sell_bid REAL NOT NULL, gross_pct REAL NOT NULL,
              net_pct REAL NOT NULL, quote_size REAL NOT NULL, estimated_net_quote REAL NOT NULL,
              mode TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              level TEXT NOT NULL, message TEXT NOT NULL, payload TEXT NOT NULL);
            """)
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db
    def opportunity(self, r):
        with self.connect() as db:
            db.execute("""INSERT INTO opportunities
            (created_at,symbol,buy_exchange,sell_exchange,buy_ask,sell_bid,gross_pct,net_pct,quote_size,estimated_net_quote,mode,payload)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(), r["symbol"], r["buy_exchange"], r["sell_exchange"],
             r["buy_ask"], r["sell_bid"], r["gross_pct"], r["net_pct"], r["quote_size"],
             r["estimated_net_quote"], r["mode"], json.dumps(r)))
    def event(self, level, message, payload=None):
        with self.connect() as db:
            db.execute("INSERT INTO events(created_at,level,message,payload) VALUES(?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), level, message, json.dumps(payload or {})))
    def latest_opportunities(self, limit=100):
        with self.connect() as db:
            return [dict(x) for x in db.execute("SELECT * FROM opportunities ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    def latest_events(self, limit=100):
        with self.connect() as db:
            return [dict(x) for x in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
