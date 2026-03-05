import logging
from dataclasses import dataclass, field

logger = logging.getLogger("trading_bot")


@dataclass
class Position:
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    amount: float
    stop_loss: float
    take_profit: float
    trailing_stop_pct: float
    highest_price: float = 0.0
    lowest_price: float = float("inf")

    def update_trailing(self, current_price: float):
        if self.trailing_stop_pct <= 0:
            return

        if self.side == "long":
            self.highest_price = max(self.highest_price, current_price)
            trailing_stop = self.highest_price * (1 - self.trailing_stop_pct)
            self.stop_loss = max(self.stop_loss, trailing_stop)
        else:
            self.lowest_price = min(self.lowest_price, current_price)
            trailing_stop = self.lowest_price * (1 + self.trailing_stop_pct)
            self.stop_loss = min(self.stop_loss, trailing_stop)

    def should_close(self, current_price: float) -> str | None:
        self.update_trailing(current_price)

        if self.side == "long":
            if current_price <= self.stop_loss:
                return "stop_loss"
            if current_price >= self.take_profit:
                return "take_profit"
        else:
            if current_price >= self.stop_loss:
                return "stop_loss"
            if current_price <= self.take_profit:
                return "take_profit"
        return None


class RiskManager:
    def __init__(self, config: dict):
        risk_cfg = config.get("risk", {})
        self.max_position_pct = risk_cfg.get("max_position_pct", 0.02)
        self.stop_loss_pct = risk_cfg.get("stop_loss_pct", 0.03)
        self.take_profit_pct = risk_cfg.get("take_profit_pct", 0.06)
        self.trailing_stop_pct = risk_cfg.get("trailing_stop_pct", 0.02)
        self.max_open_trades = risk_cfg.get("max_open_trades", 3)
        self.positions: list[Position] = []

    @property
    def open_count(self) -> int:
        return len(self.positions)

    def can_open_trade(self) -> bool:
        return self.open_count < self.max_open_trades

    def calculate_position_size(self, balance: float, price: float) -> float:
        """Risk-based position sizing: risk X% of portfolio per trade."""
        risk_amount = balance * self.max_position_pct
        amount = risk_amount / (price * self.stop_loss_pct)
        return round(amount, 8)

    def open_position(self, symbol: str, side: str, entry_price: float, amount: float) -> Position:
        if side == "long":
            sl = entry_price * (1 - self.stop_loss_pct)
            tp = entry_price * (1 + self.take_profit_pct)
        else:
            sl = entry_price * (1 + self.stop_loss_pct)
            tp = entry_price * (1 - self.take_profit_pct)

        pos = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            amount=amount,
            stop_loss=sl,
            take_profit=tp,
            trailing_stop_pct=self.trailing_stop_pct,
            highest_price=entry_price,
            lowest_price=entry_price,
        )
        self.positions.append(pos)
        logger.info(
            f"Opened {side.upper()} {amount} {symbol} @ {entry_price:.2f} | "
            f"SL: {sl:.2f} | TP: {tp:.2f}"
        )
        return pos

    def check_positions(self, current_price: float) -> list[tuple[Position, str]]:
        """Returns list of (position, reason) that should be closed."""
        to_close = []
        for pos in self.positions:
            reason = pos.should_close(current_price)
            if reason:
                to_close.append((pos, reason))
        return to_close

    def close_position(self, position: Position, exit_price: float, reason: str) -> dict:
        pnl = (exit_price - position.entry_price) * position.amount
        if position.side == "short":
            pnl = -pnl
        pnl_pct = ((exit_price / position.entry_price) - 1) * 100
        if position.side == "short":
            pnl_pct = -pnl_pct

        self.positions.remove(position)
        logger.info(
            f"Closed {position.side.upper()} {position.symbol} @ {exit_price:.2f} | "
            f"Reason: {reason} | PnL: {pnl:+.2f} ({pnl_pct:+.2f}%)"
        )
        return {"pnl": pnl, "pnl_pct": pnl_pct, "reason": reason}

    def get_position(self, symbol: str, side: str) -> Position | None:
        for pos in self.positions:
            if pos.symbol == symbol and pos.side == side:
                return pos
        return None
