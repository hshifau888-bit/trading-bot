import pandas as pd
from ta.volatility import BollingerBands

from .base import BaseStrategy, Signal


class BollingerStrategy(BaseStrategy):
    """
    Bollinger Bands Mean-Reversion Strategy.
    BUY  when price crosses above the lower band (bounce).
    SELL when price crosses below the upper band (rejection).
    """

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        period = self.params.get("bb_period", 20)
        std = self.params.get("bb_std", 2.0)
        bb = BollingerBands(df["close"], window=period, window_dev=std)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()
        return df

    def analyze(self, df: pd.DataFrame) -> str:
        df = self.add_indicators(df)
        if len(df) < 2:
            return Signal.HOLD

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        if pd.isna(curr["bb_upper"]) or pd.isna(curr["bb_lower"]):
            return Signal.HOLD

        if prev["close"] <= prev["bb_lower"] and curr["close"] > curr["bb_lower"]:
            return Signal.BUY
        if prev["close"] >= prev["bb_upper"] and curr["close"] < curr["bb_upper"]:
            return Signal.SELL

        return Signal.HOLD
