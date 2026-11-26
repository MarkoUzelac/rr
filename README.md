# Crypto Arbitrage Monitor (Telegram + Web)

A conservative, paper-first BTC / HSH cross-market spread monitor. It scans public order books through CCXT, calculates estimated net profitability after fees and a slippage buffer, stores every scan/trade simulation in SQLite, and sends alerts through Telegram.

## Important operating model

- Default mode is **PAPER**. Live orders are not enabled by this project.
- It does not promise profitable trades, a minimum profit, 500,000 fills/day, or any return.
- HSH is ambiguous by ticker. This project pins the HashCoin BEP-20 contract configured in `.env`; verify it independently before using any DEX integration.
- The HSH/USDT pool discovered during research had very low liquidity and volume. The bot's conservative default disables HSH opportunities until the operator explicitly sets appropriate thresholds.
- Exodus is a wallet, not a centralized exchange execution API. Do not put a seed phrase/private key in this app.
- Never enable withdrawal permissions on exchange API keys.

## Stack

- Python 3.11+
- FastAPI web dashboard and JSON API
- aiogram Telegram bot
- CCXT exchange market-data adapters (public order books by default)
- SQLite event ledger
- Termux-compatible shell launcher

## Termux install

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git
git clone https://github.com/MarkoUzelac/rr.git
cd rr
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python -m app
```

Open the web dashboard at `http://127.0.0.1:8080`.

## Configuration

Create a Telegram bot with @BotFather and put its token and your numeric Telegram user ID in `.env`. Configure public exchange IDs such as `kucoin,kraken,coinbase`. API keys are optional for public order-book reads. The app does not need trading keys for PAPER mode.

## Arbitrage calculation

For each venue and direction, the engine uses best bid/ask and configured fee estimates:

`net_edge = (sell_bid - buy_ask) / buy_ask - buy_fee - sell_fee - slippage_buffer`

A candidate is only a paper opportunity when the order-book depth at the configured size is sufficient and net edge exceeds the threshold. Real execution would additionally require atomic/pre-funded inventory on both venues, precision/minimum checks, fill reconciliation, partial-fill handling, latency controls and explicit operator approval.

## HSH verification

Default HashCoin (HSH) contract from project-published material:
`0xfCfEe30f631fB2D3EE8eCeb9c9E74bc92ec5B253` on BNB Smart Chain (chain ID 56).

This is a configuration hint, not a safety certification. The HSH/USDT pool snapshot observed during research showed about $750 liquidity, roughly $91 24h volume and a 1% pool fee. Such conditions are unsuitable for a high-frequency profit target. Verify live pool depth and token contract on a block explorer before any transaction.

## Security

- Keep `.env` private; it is git-ignored.
- Never paste API secrets, seed phrases, or private keys into Telegram.
- If you later add live exchange trading, create dedicated API keys with spot trading only, withdrawals disabled and IP restrictions enabled.
- Restrict dashboard binding to localhost by default.
- This tool is informational software, not financial advice.
