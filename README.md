# Crypto Arbitrage Monitor

Cross-exchange BTC spread scanner with a FastAPI dashboard and Telegram controls. The application uses public market data through CCXT and is PAPER-only: it does not submit orders or require exchange trading keys.

## Safety model

- `MODE=PAPER` is enforced in the application status and candidate records.
- No live order-placement code is included.
- Do not add wallet seed phrases, private keys, or withdrawal-enabled exchange credentials.
- Dashboard pause/resume endpoints require `DASHBOARD_CONTROL_TOKEN` in the `X-Control-Token` request header. Keep the dashboard bound to localhost unless it is placed behind authenticated HTTPS access.
- Telegram commands require the configured numeric `TELEGRAM_ALLOWED_USER_ID`.
- Estimated edge is not guaranteed profit. Fees, funding, inventory, withdrawal, transfer, latency, partial fills, market impact, precision and minimum order limits may change the result materially.

## Features

- CCXT public order-book reads for configured exchanges.
- Order-book depth walk and volume-weighted average execution prices for the configured quote size.
- Configurable taker fee and slippage estimates.
- Stale order-book rejection when exchange timestamps are available.
- Minimum net-edge filter before an opportunity is persisted.
- SQLite event and opportunity history.
- FastAPI status, opportunity and event endpoints.
- Telegram status, candidate, pause and resume commands.
- Termux launcher.

## Requirements

Python 3.11+ is recommended. Install from a clone:

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git
git clone https://github.com/MarkoUzelac/rr.git
cd rr
bash run-termux.sh
```

Edit `.env`. Generate a strong random dashboard token; do not reuse a password:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
nano .env
```

Start the app:

```bash
source .venv/bin/activate
python -m app
```

Dashboard: `http://127.0.0.1:8080`

For the pause/resume endpoints, send the token in the header:

```bash
curl -X POST http://127.0.0.1:8080/api/pause -H "X-Control-Token: YOUR_TOKEN"
curl -X POST http://127.0.0.1:8080/api/resume -H "X-Control-Token: YOUR_TOKEN"
```

## Configuration

See `.env.example`. Important settings:

- `EXCHANGES`: CCXT exchange IDs, comma-separated.
- `SYMBOLS`: market symbols supported by each venue, e.g. `BTC/USDT`.
- `ORDER_SIZE_QUOTE`: quote-currency notional used to calculate the base quantity.
- `MIN_NET_EDGE_PCT`: minimum estimated net edge required to record a candidate.
- `ESTIMATED_TAKER_FEE_PCT`: conservative fee estimate per side.
- `SLIPPAGE_BUFFER_PCT`: additional round-trip cost buffer.
- `MAX_BOOK_AGE_MS`: reject order books older than this when the exchange supplies a timestamp.
- `DASHBOARD_CONTROL_TOKEN`: secret for dashboard control routes.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID`: optional Telegram bot configuration.

## Calculation notes

The scanner walks multiple visible order-book levels for the target base quantity and calculates VWAP for both the buy asks and sell bids. It subtracts estimated fees on both legs and the configured slippage buffer. Opportunities below `MIN_NET_EDGE_PCT` are discarded.

This is still a market-data estimate, not a simulated guaranteed fill: it does not lock liquidity, account for queue position, reserve inventory, or model order latency. Venue timestamps may be missing or have different semantics, in which case age cannot be independently validated for that book.

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```

## Deployment

Keep the app private until authentication, HTTPS, rate limiting, monitoring, dependency pinning and production test coverage are in place. Do not expose the unauthenticated read-only status and history endpoints with private operational data on a public network. Live trading is intentionally out of scope.
