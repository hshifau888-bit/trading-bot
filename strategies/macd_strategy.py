import pandas as pd
from ta.trend import MACD

from .base import BaseStrategy, Signal


class MacdStrategy(BaseStrategy):
    """
    MACD Crossover Strategy.
    BUY  when MACD line crosses above signal line.
    SELL when MACD line crosses below signal line.
    """

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        fast = self.params.get("macd_fast", 12)
        slow = self.params.get("macd_slow", 26)
        signal = self.params.get("macd_signal", 9)
        macd = MACD(df["close"], window_fast=fast, window_slow=slow, window_sign=signal)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()
        return df

    def analyze(self, df: pd.DataFrame) -> str:
        df = self.add_indicators(df)
        if len(df) < 2:
            return Signal.HOLD

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        if pd.isna(curr["macd"]) or pd.isna(curr["macd_signal"]):
            return Signal.HOLD

        prev_above = prev["macd"] > prev["macd_signal"]
        curr_above = curr["macd"] > curr["macd_signal"]

        if not prev_above and curr_above:
            return Signal.BUY
        if prev_above and not curr_above:
            return Signal.SELL

        return Signal.HOLD
