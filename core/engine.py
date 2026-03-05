import time
import logging
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table

from core.exchange import ExchangeConnector
from core.risk_manager import RiskManager
from strategies.base import BaseStrategy, Signal

logger = logging.getLogger("trading_bot")
console = Console()


class PaperAccount:
    """Simulated account for paper trading."""

    def __init__(self, balance: float = 10000.0):
        self.balance = balance
        self.initial_balance = balance
        self.positions: dict[str, dict] = {}
        self.trade_history: list[dict] = []

    def buy(self, symbol: str, amount: float, price: float):
        cost = amount * price
        if cost > self.balance:
            amount = self.balance / price
            cost = amount * price
        self.balance -= cost
        self.positions[symbol] = {"amount": amount, "entry_price": price, "side": "long"}
        logger.info(f"[PAPER] BUY {amount:.6f} {symbol} @ {price:.2f} (cost: ${cost:.2f})")

    def sell(self, symbol: str, price: float):
        if symbol not in self.positions:
            return
        pos = self.positions.pop(symbol)
        revenue = pos["amount"] * price
        pnl = revenue - (pos["amount"] * pos["entry_price"])
        self.balance += revenue
        trade = {
            "symbol": symbol,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": price,
            "amount": pos["amount"],
            "pnl": pnl,
            "time": datetime.now().isoformat(),
        }
        self.trade_history.append(trade)
        logger.info(f"[PAPER] SELL {pos['amount']:.6f} {symbol} @ {price:.2f} | PnL: ${pnl:+.2f}")

    @property
    def equity(self) -> float:
        return self.balance


class TradingEngine:
    def __init__(self, config: dict, strategy: BaseStrategy, exchange: ExchangeConnector):
        self.config = config
        self.strategy = strategy
        self.exchange = exchange
        self.risk_manager = RiskManager(config)
        self.mode = config.get("mode", "paper")
        self.symbol = config["trading"]["symbol"]
        self.timeframe = config["trading"]["timeframe"]
        self.candle_limit = config["trading"].get("candle_limit", 200)
        self.poll_interval = config.get("poll_interval_seconds", 60)

        if self.mode == "paper":
            bt_balance = config.get("backtest", {}).get("initial_balance", 10000)
            self.paper = PaperAccount(balance=bt_balance)
        else:
            self.paper = None

    def _get_price(self) -> float:
        ticker = self.exchange.fetch_ticker(self.symbol)
        return ticker["last"]

    def _get_balance(self) -> float:
        if self.paper:
            return self.paper.equity
        bal = self.exchange.fetch_balance()
        quote = self.symbol.split("/")[1]
        return bal.get("free", {}).get(quote, 0)

    def _execute_buy(self, amount: float, price: float):
        if self.paper:
            self.paper.buy(self.symbol, amount, price)
        else:
            self.exchange.create_market_buy(self.symbol, amount)

    def _execute_sell(self, price: float):
        if self.paper:
            self.paper.sell(self.symbol, price)
        else:
            pos = self.risk_manager.get_position(self.symbol, "long")
            if pos:
                self.exchange.create_market_sell(self.symbol, pos.amount)

    def _print_status(self, signal: str, price: float, balance: float):
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()

        mode_label = f"[yellow]{self.mode.upper()}[/yellow]"
        signal_colors = {"buy": "green", "sell": "red", "hold": "dim"}
        signal_label = f"[{signal_colors.get(signal, 'white')}]{signal.upper()}[/{signal_colors.get(signal, 'white')}]"

        table.add_row("Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Mode", mode_label)
        table.add_row("Symbol", self.symbol)
        table.add_row("Price", f"${price:,.2f}")
        table.add_row("Signal", signal_label)
        table.add_row("Balance", f"${balance:,.2f}")
        table.add_row("Open Positions", str(self.risk_manager.open_count))
        console.print(table)
        console.print("─" * 50)

    def run(self):
        console.print(f"\n[bold cyan]Trading Bot Started[/bold cyan] — {self.mode.upper()} mode")
        console.print(f"Symbol: {self.symbol} | Timeframe: {self.timeframe}")
        console.print(f"Strategy: {self.config['strategy']['name']}")
        console.print("─" * 50)

        try:
            while True:
                try:
                    df = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, self.candle_limit)
                    price = df["close"].iloc[-1]
                    balance = self._get_balance()

                    to_close = self.risk_manager.check_positions(price)
                    for pos, reason in to_close:
                        self._execute_sell(price)
                        self.risk_manager.close_position(pos, price, reason)

                    signal = self.strategy.analyze(df)
                    self._print_status(signal, price, balance)

                    if signal == Signal.BUY and self.risk_manager.can_open_trade():
                        existing = self.risk_manager.get_position(self.symbol, "long")
                        if existing is None:
                            amount = self.risk_manager.calculate_position_size(balance, price)
                            if amount > 0:
                                self._execute_buy(amount, price)
                                self.risk_manager.open_position(self.symbol, "long", price, amount)

                    elif signal == Signal.SELL:
                        existing = self.risk_manager.get_position(self.symbol, "long")
                        if existing:
                            self._execute_sell(price)
                            self.risk_manager.close_position(existing, price, "signal_sell")

                except Exception as e:
                    logger.error(f"Cycle error: {e}", exc_info=True)

                logger.debug(f"Sleeping {self.poll_interval}s until next cycle...")
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Bot stopped by user.[/bold yellow]")
            if self.paper:
                console.print(f"Final balance: ${self.paper.equity:,.2f}")
                console.print(f"Total trades: {len(self.paper.trade_history)}")
                total_pnl = sum(t["pnl"] for t in self.paper.trade_history)
                console.print(f"Total PnL: ${total_pnl:+,.2f}")
