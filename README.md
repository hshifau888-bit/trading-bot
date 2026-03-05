# Trading Bot

A modular, research-backed cryptocurrency trading bot with multiple strategies, risk management, backtesting, and paper/live trading modes.

> **Disclaimer:** This bot is for educational purposes. Algorithmic trading carries significant financial risk. Never trade with money you cannot afford to lose. Past backtest performance does not guarantee future results.

## Features

- **5 Built-in Strategies** — SMA Crossover, RSI, MACD, Bollinger Bands, and the research-based **Alpha Composite**
- **Alpha Composite Strategy** — Multi-signal system combining EMA trend filter, ADX strength, RSI + MACD momentum, volume confirmation, and Bollinger squeeze detection
- **ATR-Adaptive Exits** — Stop-loss and take-profit that scale with current market volatility
- **Risk Management** — Fractional Kelly position sizing, trailing stops, max position limits
- **Backtesting Engine** — Test strategies on historical data with detailed metrics and strategy comparison
- **Paper Trading** — Simulate trades with fake money to validate before going live
- **100+ Exchanges** — Powered by CCXT (Binance, Coinbase, Kraken, etc.)
- **Full Market Research** — See `MARKET_RESEARCH.md` for the data behind every design decision

## Quick Start

```bash
cd trading-bot

# Install dependencies
pip install -r requirements.txt

# Copy environment template and add your API keys
cp .env.example .env

# Run a backtest with the default strategy (Alpha Composite)
python3 main.py backtest

# Backtest all strategies and compare side-by-side
python3 main.py backtest --all

# Backtest on a specific pair and timeframe
python3 main.py backtest --all --symbol ETH/USDT --timeframe 4h

# Start paper trading
python3 main.py trade
```

## Configuration

Edit `config.yaml` to customize:

| Setting | Description | Recommended |
|---|---|---|
| `mode` | `paper` (simulated) or `live` (real money) | Start with `paper` |
| `exchange.name` | Any CCXT exchange (binance, kraken, coinbase) | `kraken` or `binance` |
| `trading.symbol` | Trading pair, e.g. `BTC/USDT` | `BTC/USDT` |
| `trading.timeframe` | Candle interval | `4h` (research-backed) |
| `trading.candle_limit` | Candles to fetch (need 200+ for EMA warmup) | `720` |
| `strategy.name` | Strategy to use | `alpha_composite` |
| `risk.max_position_pct` | % of portfolio risked per trade | `0.015` (1.5%) |

## Strategies

### Alpha Composite (Recommended)

A 5-layer signal confirmation system built from market research. See `MARKET_RESEARCH.md` for full details.

**Layers:**
1. **Trend Filter** (EMA 50/200 + ADX > 20) — only trade with the trend
2. **Momentum** (RSI + MACD dual confirmation) — precise entry timing
3. **Volume** (above 1.1x average) — real market participation
4. **Regime Detection** (Bollinger Bandwidth) — skip low-volatility squeezes
5. **ATR Exits** — volatility-adaptive stop-loss, take-profit, and trailing stop

**Backtest Results (BTC/USDT 4h, 120 days including a ~37% crash):**
- Return: +3.22% | Max Drawdown: 3.1% | Sharpe: 3.49 | Profit Factor: 1.61
- Lowest drawdown of any strategy tested

### SMA Crossover
Buys when fast SMA crosses above slow SMA. Simple trend-following.

### RSI (Relative Strength Index)
Buys on RSI recovery from oversold (<30), sells on reversal from overbought (>70). Mean-reversion.

### MACD
Buys on MACD line crossing above signal line. Momentum + trend.

### Bollinger Bands
Buys on lower band bounce, sells on upper band rejection. Mean-reversion in ranging markets.

## Strategy Comparison (BTC/USDT 4h, Nov 2025 - Mar 2026)

| Strategy | Return | Win Rate | Trades | Max Drawdown | Sharpe |
|---|---|---|---|---|---|
| Bollinger | +18.31% | 48% | 33 | 6.0% | 4.86 |
| MACD | +7.17% | 39% | 33 | 6.6% | 1.83 |
| **Alpha Composite** | **+3.22%** | **43%** | **7** | **3.1%** | **3.49** |
| SMA Crossover | +0.59% | 37% | 27 | 6.4% | 0.21 |
| RSI | -0.44% | 43% | 28 | 11.3% | -0.14 |

## Project Structure

```
trading-bot/
├── main.py                     # CLI entrypoint
├── config.yaml                 # Bot configuration
├── MARKET_RESEARCH.md          # Full market research and strategy analysis
├── .env.example                # API key template
├── requirements.txt            # Python dependencies
├── core/
│   ├── exchange.py             # CCXT exchange connector
│   ├── engine.py               # Live/paper trading engine
│   ├── risk_manager.py         # Position sizing and risk controls
│   └── backtester.py           # Backtesting engine with ATR support
├── strategies/
│   ├── base.py                 # Strategy interface
│   ├── alpha_composite.py      # Research-based multi-signal strategy
│   ├── sma_crossover.py        # SMA Crossover strategy
│   ├── rsi_strategy.py         # RSI strategy
│   ├── macd_strategy.py        # MACD strategy
│   └── bollinger_strategy.py   # Bollinger Bands strategy
└── utils/
    ├── config_loader.py        # YAML + .env config loading
    └── logger.py               # Logging setup
```

## Risk Management

- **Fractional Kelly Sizing**: Risks 1.5% of portfolio per trade (configurable). Based on research showing 0.25-0.5x Kelly is optimal for crypto.
- **ATR-Adaptive Stops**: Stop-loss at 2x ATR, take-profit at 3x ATR — scales with volatility automatically.
- **Trailing Stop**: ATR-based trailing stop locks in profits as price moves favorably.
- **Max Open Trades**: Limits concurrent positions (default 2) to control correlation risk.

## Adding a Custom Strategy

1. Create a new file in `strategies/`:

```python
from strategies.base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def add_indicators(self, df):
        # Add your indicators to the dataframe
        return df

    def analyze(self, df):
        # Return Signal.BUY, Signal.SELL, or Signal.HOLD
        return Signal.HOLD
```

2. Register it in `strategies/__init__.py`:

```python
from .my_strategy import MyStrategy
STRATEGIES["my_strategy"] = MyStrategy
```

3. Set `strategy.name: my_strategy` in `config.yaml`.

## Market Research

See **`MARKET_RESEARCH.md`** for the comprehensive research report including:
- Current crypto market conditions and macro drivers
- Analysis of top-performing algorithmic strategies (2025-2026)
- Evidence behind each design decision in the Alpha Composite strategy
- Position sizing research (Kelly criterion)
- ATR stop-loss optimization data
- Full backtest results across multiple assets and timeframes
