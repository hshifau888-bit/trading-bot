import pandas as pd
from ta.momentum import RSIIndicator

from .base import BaseStrategy, Signal


class RsiStrategy(BaseStrategy):
    """
    RSI Mean-Reversion Strategy.
    BUY  when RSI crosses above oversold threshold (recovery).
    SELL when RSI crosses below overbought threshold (reversal).
    """

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        period = self.params.get("rsi_period", 14)
        df["rsi"] = RSIIndicator(df["close"], window=period).rsi()
        return df

    def analyze(self, df: pd.DataFrame) -> str:
        df = self.add_indicators(df)
        if len(df) < 2:
            return Signal.HOLD

        overbought = self.params.get("rsi_overbought", 70)
        oversold = self.params.get("rsi_oversold", 30)

        prev_rsi = df["rsi"].iloc[-2]
        curr_rsi = df["rsi"].iloc[-1]

        if pd.isna(prev_rsi) or pd.isna(curr_rsi):
            return Signal.HOLD

        if prev_rsi <= oversold and curr_rsi > oversold:
            return Signal.BUY
        if prev_rsi >= overbought and curr_rsi < overbought:
            return Signal.SELL

        return Signal.HOLD
