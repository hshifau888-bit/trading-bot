import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from strategies.base import BaseStrategy, Signal

logger = logging.getLogger("trading_bot")
console = Console()


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None = None
    side: str = "long"
    entry_price: float = 0.0
    exit_price: float = 0.0
    amount: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    strategy_name: str = ""
    initial_balance: float = 0.0
    final_balance: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    trades: list[Trade] = field(default_factory=list)

    def display(self):
        title = f"Backtest: {self.strategy_name}" if self.strategy_name else "Backtest Results"
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        ret_pct = ((self.final_balance / self.initial_balance) - 1) * 100 if self.initial_balance else 0

        table.add_row("Initial Balance", f"${self.initial_balance:,.2f}")
        table.add_row("Final Balance", f"${self.final_balance:,.2f}")
        table.add_row("Total Return", f"{ret_pct:+.2f}%")
        table.add_row("Total PnL", f"${self.total_pnl:+,.2f}")
        table.add_row("───────────────", "───────────")
        table.add_row("Total Trades", str(self.total_trades))
        table.add_row("Winning Trades", str(self.winning_trades))
        table.add_row("Losing Trades", str(self.losing_trades))
        table.add_row("Win Rate", f"{self.win_rate:.1f}%")
        table.add_row("Profit Factor", f"{self.profit_factor:.2f}")
        table.add_row("───────────────", "───────────")
        table.add_row("Avg Trade PnL", f"${self.avg_trade_pnl:+,.2f}")
        table.add_row("Avg Win", f"${self.avg_win:+,.2f}")
        table.add_row("Avg Loss", f"${self.avg_loss:+,.2f}")
        table.add_row("Largest Win", f"${self.largest_win:+,.2f}")
        table.add_row("Largest Loss", f"${self.largest_loss:+,.2f}")
        table.add_row("───────────────", "───────────")
        table.add_row("Max Drawdown", f"{self.max_drawdown_pct:.2f}%")
        table.add_row("Sharpe Ratio", f"{self.sharpe_ratio:.2f}")

        console.print(table)


class Backtester:
    def __init__(self, config: dict, strategy: BaseStrategy):
        self.config = config
        self.strategy = strategy
        risk = config.get("risk", {})
        self.stop_loss_pct = risk.get("stop_loss_pct", 0.03)
        self.take_profit_pct = risk.get("take_profit_pct", 0.06)
        self.max_position_pct = risk.get("max_position_pct", 0.02)
        self.trailing_stop_pct = risk.get("trailing_stop_pct", 0.02)
        self.use_atr_stops = risk.get("use_atr_stops", False)

    def _get_atr_stops(self, df: pd.DataFrame, entry_price: float, side: str) -> dict | None:
        if not self.use_atr_stops:
            return None
        if not hasattr(self.strategy, "get_atr_stops"):
            return None
        return self.strategy.get_atr_stops(df, entry_price, side)

    def run(self, df: pd.DataFrame, initial_balance: float = 10000.0,
            strategy_name: str = "") -> BacktestResult:
        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown_pct = 0.0
        trades: list[Trade] = []
        open_trade: Trade | None = None
        stop_loss = 0.0
        take_profit = 0.0
        highest_since_entry = 0.0
        atr_at_entry = 0.0
        returns = []

        df = self.strategy.add_indicators(df.copy())

        for i in range(1, len(df)):
            window = df.iloc[: i + 1].copy()
            current = df.iloc[i]
            price = current["close"]

            if open_trade is not None:
                close_reason = None

                # ATR-adaptive trailing stop
                atr_trail_mult = self.strategy.params.get("atr_trail_multiplier", 2.5)
                current_atr = current.get("atr", atr_at_entry) if "atr" in df.columns else atr_at_entry
                if pd.isna(current_atr) or current_atr <= 0:
                    current_atr = atr_at_entry

                if open_trade.side == "long":
                    highest_since_entry = max(highest_since_entry, price)
                    if self.use_atr_stops and atr_at_entry > 0:
                        trailing = highest_since_entry - (current_atr * atr_trail_mult)
                        stop_loss = max(stop_loss, trailing)
                    elif self.trailing_stop_pct > 0:
                        trailing = highest_since_entry * (1 - self.trailing_stop_pct)
                        stop_loss = max(stop_loss, trailing)

                    if price <= stop_loss:
                        close_reason = "stop_loss"
                    elif price >= take_profit:
                        close_reason = "take_profit"
                else:
                    highest_since_entry = min(highest_since_entry, price)
                    if self.use_atr_stops and atr_at_entry > 0:
                        trailing = highest_since_entry + (current_atr * atr_trail_mult)
                        stop_loss = min(stop_loss, trailing)
                    elif self.trailing_stop_pct > 0:
                        trailing = highest_since_entry * (1 + self.trailing_stop_pct)
                        stop_loss = min(stop_loss, trailing)

                    if price >= stop_loss:
                        close_reason = "stop_loss"
                    elif price <= take_profit:
                        close_reason = "take_profit"

                signal = self.strategy.analyze(window)
                if open_trade.side == "long" and signal == Signal.SELL:
                    close_reason = "signal_sell"
                elif open_trade.side == "short" and signal == Signal.BUY:
                    close_reason = "signal_buy"

                if close_reason:
                    open_trade.exit_price = price
                    open_trade.exit_time = current.name
                    open_trade.reason = close_reason

                    if open_trade.side == "long":
                        open_trade.pnl = (price - open_trade.entry_price) * open_trade.amount
                    else:
                        open_trade.pnl = (open_trade.entry_price - price) * open_trade.amount

                    open_trade.pnl_pct = (open_trade.pnl / (open_trade.entry_price * open_trade.amount)) * 100
                    balance += open_trade.pnl
                    returns.append(open_trade.pnl / initial_balance)
                    trades.append(open_trade)
                    open_trade = None

            else:
                signal = self.strategy.analyze(window)

                if signal in (Signal.BUY, Signal.SELL):
                    side = "long" if signal == Signal.BUY else "short"

                    atr_stops = self._get_atr_stops(window, price, side)

                    if atr_stops:
                        stop_loss = atr_stops["stop_loss"]
                        take_profit = atr_stops["take_profit"]
                        atr_at_entry = atr_stops["atr"]
                        sl_distance_pct = abs(price - stop_loss) / price
                    else:
                        atr_at_entry = 0.0
                        sl_distance_pct = self.stop_loss_pct
                        if side == "long":
                            stop_loss = price * (1 - self.stop_loss_pct)
                            take_profit = price * (1 + self.take_profit_pct)
                        else:
                            stop_loss = price * (1 + self.stop_loss_pct)
                            take_profit = price * (1 - self.take_profit_pct)

                    risk_amount = balance * self.max_position_pct
                    sl_distance_pct = max(sl_distance_pct, 0.005)
                    amount = risk_amount / (price * sl_distance_pct)

                    highest_since_entry = price

                    open_trade = Trade(
                        entry_time=current.name,
                        side=side,
                        entry_price=price,
                        amount=amount,
                    )

            peak_balance = max(peak_balance, balance)
            dd = ((peak_balance - balance) / peak_balance) * 100 if peak_balance > 0 else 0
            max_drawdown_pct = max(max_drawdown_pct, dd)

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))

        sharpe = 0.0
        if returns:
            arr = np.array(returns)
            if arr.std() > 0:
                sharpe = (arr.mean() / arr.std()) * (252 ** 0.5)

        avg_trade_pnl = np.mean([t.pnl for t in trades]) if trades else 0
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = np.mean([t.pnl for t in losing]) if losing else 0
        largest_win = max((t.pnl for t in trades), default=0)
        largest_loss = min((t.pnl for t in trades), default=0)

        result = BacktestResult(
            strategy_name=strategy_name,
            initial_balance=initial_balance,
            final_balance=round(balance, 2),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=round(sum(t.pnl for t in trades), 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            win_rate=round((len(winning) / len(trades) * 100) if trades else 0, 1),
            profit_factor=round(gross_profit / gross_loss if gross_loss > 0 else 0, 2),
            sharpe_ratio=round(sharpe, 2),
            avg_trade_pnl=round(avg_trade_pnl, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            trades=trades,
        )

        return result
