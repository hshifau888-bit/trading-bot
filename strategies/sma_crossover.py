import pandas as pd
from ta.trend import SMAIndicator

from .base import BaseStrategy, Signal


class SmaCrossoverStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover.
    BUY  when fast SMA crosses above slow SMA.
    SELL when fast SMA crosses below slow SMA.
    """

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        fast = self.params.get("fast_period", 10)
        slow = self.params.get("slow_period", 30)
        df["sma_fast"] = SMAIndicator(df["close"], window=fast).sma_indicator()
        df["sma_slow"] = SMAIndicator(df["close"], window=slow).sma_indicator()
        return df

    def analyze(self, df: pd.DataFrame) -> str:
        df = self.add_indicators(df)
        if len(df) < 2:
            return Signal.HOLD

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        if pd.isna(curr["sma_fast"]) or pd.isna(curr["sma_slow"]):
            return Signal.HOLD

        prev_above = prev["sma_fast"] > prev["sma_slow"]
        curr_above = curr["sma_fast"] > curr["sma_slow"]

        if not prev_above and curr_above:
            return Signal.BUY
        if prev_above and not curr_above:
            return Signal.SELL

        return Signal.HOLD
