#!/usr/bin/env python3
"""
Trading Bot — CLI Entrypoint
Usage:
    python main.py trade              # Run live/paper trading (based on config)
    python main.py backtest           # Run backtest on historical data
    python main.py backtest --all     # Backtest all strategies and compare
"""

import argparse
import sys

from rich.console import Console

from utils.config_loader import load_config
from utils.logger import setup_logger
from strategies import get_strategy, STRATEGIES
from core.exchange import ExchangeConnector
from core.backtester import Backtester
from core.engine import TradingEngine

console = Console()


def cmd_trade(config: dict):
    strategy = get_strategy(config["strategy"]["name"], config["strategy"]["params"])
    exchange = ExchangeConnector(config)
    engine = TradingEngine(config, strategy, exchange)
    engine.run()


def cmd_backtest(config: dict, all_strategies: bool = False):
    exchange = ExchangeConnector(config)
    symbol = config["trading"]["symbol"]
    timeframe = config["trading"]["timeframe"]
    limit = config["trading"].get("candle_limit", 200)
    initial_balance = config.get("backtest", {}).get("initial_balance", 10000)

    console.print(f"\n[bold cyan]Fetching {limit} candles of {symbol} ({timeframe})...[/bold cyan]")
    df = exchange.fetch_ohlcv(symbol, timeframe, limit)
    console.print(f"Data range: {df.index[0]} → {df.index[-1]} ({len(df)} candles)\n")

    strategies_to_test = {}
    if all_strategies:
        for name in STRATEGIES:
            strategies_to_test[name] = get_strategy(name, config["strategy"]["params"])
    else:
        name = config["strategy"]["name"]
        strategies_to_test[name] = get_strategy(name, config["strategy"]["params"])

    results = []
    for name, strategy in strategies_to_test.items():
        bt = Backtester(config, strategy)
        result = bt.run(df.copy(), initial_balance, strategy_name=name)
        result.display()
        results.append(result)
        console.print()

    if len(results) > 1:
        console.print("[bold cyan]Strategy Comparison Summary[/bold cyan]")
        from rich.table import Table
        cmp = Table(show_header=True, header_style="bold magenta")
        cmp.add_column("Strategy")
        cmp.add_column("Return %", justify="right")
        cmp.add_column("Win Rate", justify="right")
        cmp.add_column("Trades", justify="right")
        cmp.add_column("Profit Factor", justify="right")
        cmp.add_column("Max DD %", justify="right")
        cmp.add_column("Sharpe", justify="right")
        for r in sorted(results, key=lambda x: x.final_balance, reverse=True):
            ret = ((r.final_balance / r.initial_balance) - 1) * 100
            style = "green" if ret > 0 else "red"
            cmp.add_row(
                f"[{style}]{r.strategy_name}[/{style}]",
                f"[{style}]{ret:+.2f}%[/{style}]",
                f"{r.win_rate:.0f}%",
                str(r.total_trades),
                f"{r.profit_factor:.2f}",
                f"{r.max_drawdown_pct:.1f}%",
                f"{r.sharpe_ratio:.2f}",
            )
        console.print(cmp)


def main():
    parser = argparse.ArgumentParser(description="Trading Bot")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("trade", help="Run the trading bot (live or paper mode)")

    bt_parser = subparsers.add_parser("backtest", help="Run backtests on historical data")
    bt_parser.add_argument("--all", action="store_true", help="Test all strategies and compare")
    bt_parser.add_argument("--strategy", type=str, help="Override strategy from config")
    bt_parser.add_argument("--symbol", type=str, help="Override symbol from config")
    bt_parser.add_argument("--timeframe", type=str, help="Override timeframe from config")

    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    if args.command == "backtest":
        if args.strategy:
            config["strategy"]["name"] = args.strategy
        if args.symbol:
            config["trading"]["symbol"] = args.symbol
        if args.timeframe:
            config["trading"]["timeframe"] = args.timeframe

    setup_logger(config)

    console.print("[bold green]Trading Bot v1.0[/bold green]")
    console.print(f"Mode: {config.get('mode', 'paper').upper()}")

    if args.command == "trade":
        cmd_trade(config)
    elif args.command == "backtest":
        cmd_backtest(config, all_strategies=args.all)


if __name__ == "__main__":
    main()
