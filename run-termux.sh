#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
pkg update -y
pkg install -y python
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
echo "Edit .env, set Telegram token and allowed Telegram user ID."
echo "Then run: source .venv/bin/activate && python -m app"
