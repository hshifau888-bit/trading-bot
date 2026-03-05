from abc import ABC, abstractmethod
import pandas as pd


class Signal:
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseStrategy(ABC):
    def __init__(self, params: dict):
        self.params = params

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> str:
        """Analyze OHLCV data and return a Signal (BUY / SELL / HOLD)."""
        ...

    @abstractmethod
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add strategy-specific indicators to the dataframe."""
        ...
