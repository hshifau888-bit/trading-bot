#!/bin/bash
# ─────────────────────────────────────────────
# Trading Bot — Quick Setup Script
# ─────────────────────────────────────────────

set -e

echo "==================================="
echo "  Trading Bot Setup"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Install it from https://python.org/downloads"
    exit 1
fi

echo "[1/3] Installing dependencies..."
pip3 install -r requirements.txt --quiet

echo "[2/3] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "       Created .env file — add your Bybit API keys there."
else
    echo "       .env already exists, skipping."
fi

mkdir -p logs

echo "[3/3] Testing connection..."
python3 -c "
import ccxt
exchange = ccxt.bybit({'enableRateLimit': True})
exchange.load_markets()
ohlcv = exchange.fetch_ohlcv('BTC/USDT', '4h', limit=3)
price = ohlcv[-1][4]
print(f'       Connected to Bybit! BTC/USDT = \${price:,.2f}')
"

echo ""
echo "==================================="
echo "  Setup complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "  1. Add your Bybit API keys to .env"
echo "  2. Run a backtest:  python3 main.py backtest --all"
echo "  3. Paper trade:     python3 main.py trade"
echo ""
