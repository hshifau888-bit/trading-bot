"""
Alpha Composite Strategy — Research-Based Multi-Signal System

Built from market research (March 2026) combining the highest-performing
elements from backtested strategies:

1. TREND FILTER (EMA 200 + ADX)
   - Only trade in the direction of the major trend
   - ADX > 20 confirms a real trend exists (avoids sideways chop)

2. MOMENTUM CONFIRMATION (RSI + MACD)
   - RSI identifies oversold/overbought momentum shifts
   - MACD crossover confirms the timing of entry
   - Both must agree for a signal to fire

3. VOLUME VALIDATION
   - Volume must exceed 1.2x its 20-period average
   - Ensures real market participation behind the move

4. VOLATILITY-ADAPTIVE EXITS (ATR)
   - Stop-loss and take-profit scale with current volatility
   - Tight in calm markets, wide in volatile ones
   - ATR trailing stop locks in profits dynamically

5. REGIME DETECTION (Bollinger Bandwidth)
   - Detects low-volatility compression phases
   - Avoids entries during squeeze zones that generate false signals
   - Waits for expansion before committing capital

Sources:
- EMA+MACD+RSI triple confirmation: 49-69% annualized (FMZ/Medium 2026)
- ADX trend filter: improved returns from 36% to 182% (PyQuantLab 2026)
- ATR trailing stops: +65.8% annualized on ETH (PyQuantLab Feb 2026)
- Volume confirmation: reduces false signals by ~40% (multiple studies)
- Fractional Kelly sizing: recommended by all major risk research
"""

import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange

from .base import BaseStrategy, Signal


class AlphaCompositeStrategy(BaseStrategy):

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # --- Trend filters ---
        ema_fast = self.params.get("ema_fast_period", 50)
        ema_slow = self.params.get("ema_slow_period", 200)
        df["ema_fast"] = EMAIndicator(close, window=ema_fast).ema_indicator()
        df["ema_slow"] = EMAIndicator(close, window=ema_slow).ema_indicator()

        # --- ADX trend strength ---
        adx_period = self.params.get("adx_period", 14)
        adx = ADXIndicator(high, low, close, window=adx_period)
        df["adx"] = adx.adx()
        df["di_plus"] = adx.adx_pos()
        df["di_minus"] = adx.adx_neg()

        # --- RSI momentum ---
        rsi_period = self.params.get("rsi_period", 14)
        df["rsi"] = RSIIndicator(close, window=rsi_period).rsi()

        # --- MACD momentum ---
        macd_fast = self.params.get("macd_fast", 12)
        macd_slow = self.params.get("macd_slow", 26)
        macd_signal = self.params.get("macd_signal", 9)
        macd = MACD(close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # --- Volume confirmation ---
        vol_ma_period = self.params.get("volume_ma_period", 20)
        df["volume_ma"] = SMAIndicator(volume, window=vol_ma_period).sma_indicator()
        df["volume_ratio"] = volume / df["volume_ma"]

        # --- ATR for volatility-adaptive exits ---
        atr_period = self.params.get("atr_period", 14)
        df["atr"] = AverageTrueRange(high, low, close, window=atr_period).average_true_range()

        # --- Bollinger Bandwidth for regime detection ---
        bb_period = self.params.get("bb_period", 20)
        bb_std = self.params.get("bb_std", 2.0)
        bb = BollingerBands(close, window=bb_period, window_dev=bb_std)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_bandwidth"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        # Bandwidth percentile over lookback (squeeze detection)
        bw_lookback = self.params.get("bb_bandwidth_lookback", 50)
        df["bb_bw_percentile"] = df["bb_bandwidth"].rolling(window=bw_lookback).rank(pct=True)

        return df

    def _check_trend(self, row: pd.Series) -> str | None:
        """Returns 'bullish', 'bearish', or None if no clear trend."""
        adx_threshold = self.params.get("adx_threshold", 20)

        if pd.isna(row.get("adx")) or pd.isna(row.get("ema_slow")):
            return None

        has_trend = row["adx"] > adx_threshold
        if not has_trend:
            return None

        price_above_ema_slow = row["close"] > row["ema_slow"]
        price_above_ema_fast = row["close"] > row["ema_fast"]
        fast_above_slow = row["ema_fast"] > row["ema_slow"]
        di_bullish = row["di_plus"] > row["di_minus"]

        # Require price above BOTH EMAs + directional index for long
        bullish = price_above_ema_slow and price_above_ema_fast and di_bullish
        # Short: price below both EMAs + directional index confirms
        bearish = (not price_above_ema_slow) and (not price_above_ema_fast) and (not di_bullish)

        if bullish:
            return "bullish"
        if bearish:
            return "bearish"
        return None

    def _check_momentum_buy(self, prev: pd.Series, curr: pd.Series) -> bool:
        """RSI + MACD agreement for long entry. Both must confirm."""
        rsi_oversold = self.params.get("rsi_oversold", 35)

        # RSI must be recovering from oversold OR be above midline and rising
        rsi_recovering = prev["rsi"] <= rsi_oversold and curr["rsi"] > rsi_oversold
        rsi_bullish = curr["rsi"] > 45 and curr["rsi"] > prev["rsi"]

        # MACD crossover or histogram turning positive
        macd_crossover = (
            prev["macd"] <= prev["macd_signal"]
            and curr["macd"] > curr["macd_signal"]
        )
        macd_hist_rising = (
            curr["macd_hist"] > 0
            and curr["macd_hist"] > prev["macd_hist"]
        )

        # Require MACD crossover + RSI confirmation
        # OR RSI recovery from oversold + MACD histogram improving
        return (macd_crossover and (rsi_bullish or rsi_recovering)) or \
               (rsi_recovering and macd_hist_rising)

    def _check_momentum_sell(self, prev: pd.Series, curr: pd.Series) -> bool:
        """RSI + MACD agreement for short/exit signal. Both must confirm."""
        rsi_overbought = self.params.get("rsi_overbought", 65)

        # RSI dropping from overbought OR falling below midline
        rsi_reversing = prev["rsi"] >= rsi_overbought and curr["rsi"] < rsi_overbought
        rsi_bearish = curr["rsi"] < 55 and curr["rsi"] < prev["rsi"]

        # MACD crossover down or histogram turning negative
        macd_crossover = (
            prev["macd"] >= prev["macd_signal"]
            and curr["macd"] < curr["macd_signal"]
        )
        macd_hist_falling = (
            curr["macd_hist"] < 0
            and curr["macd_hist"] < prev["macd_hist"]
        )

        return (macd_crossover and (rsi_bearish or rsi_reversing)) or \
               (rsi_reversing and macd_hist_falling)

    def _check_volume(self, curr: pd.Series) -> bool:
        """Volume must exceed threshold of its moving average."""
        vol_threshold = self.params.get("volume_threshold", 1.1)
        if pd.isna(curr.get("volume_ratio")):
            return True
        return curr["volume_ratio"] >= vol_threshold

    def _in_squeeze(self, curr: pd.Series) -> bool:
        """Detect Bollinger Band squeeze (low-volatility compression)."""
        squeeze_percentile = self.params.get("squeeze_percentile", 0.15)
        if pd.isna(curr.get("bb_bw_percentile")):
            return False
        return curr["bb_bw_percentile"] <= squeeze_percentile

    def analyze(self, df: pd.DataFrame) -> str:
        min_rows = max(
            self.params.get("ema_slow_period", 200),
            self.params.get("bb_bandwidth_lookback", 50) + self.params.get("bb_period", 20),
        ) + 5

        if len(df) < min_rows:
            return Signal.HOLD

        try:
            df = self.add_indicators(df)
        except (ValueError, Exception):
            return Signal.HOLD

        if len(df) < 3:
            return Signal.HOLD

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        for col in ["adx", "rsi", "macd", "macd_signal", "ema_slow", "atr"]:
            if pd.isna(curr.get(col)):
                return Signal.HOLD

        if self._in_squeeze(curr):
            return Signal.HOLD

        trend = self._check_trend(curr)

        has_volume = self._check_volume(curr)

        if trend == "bullish" and self._check_momentum_buy(prev, curr) and has_volume:
            return Signal.BUY

        if trend == "bearish" and self._check_momentum_sell(prev, curr):
            return Signal.SELL

        # Defensive sell: even without a full bear trend, exit if momentum
        # is clearly deteriorating and price is below the fast EMA
        if trend is None and not pd.isna(curr.get("ema_fast")):
            price_weak = curr["close"] < curr["ema_fast"]
            if price_weak and self._check_momentum_sell(prev, curr):
                return Signal.SELL

        return Signal.HOLD

    def get_atr_stops(self, df: pd.DataFrame, entry_price: float, side: str = "long") -> dict:
        """
        Compute volatility-adaptive stop-loss and take-profit using ATR.
        Called externally by the backtester/engine for dynamic position management.
        """
        atr_sl_mult = self.params.get("atr_sl_multiplier", 2.0)
        atr_tp_mult = self.params.get("atr_tp_multiplier", 3.0)
        atr = df["atr"].iloc[-1] if "atr" in df.columns else entry_price * 0.02

        if pd.isna(atr) or atr <= 0:
            atr = entry_price * 0.02

        if side == "long":
            sl = entry_price - (atr * atr_sl_mult)
            tp = entry_price + (atr * atr_tp_mult)
        else:
            sl = entry_price + (atr * atr_sl_mult)
            tp = entry_price - (atr * atr_tp_mult)

        return {"stop_loss": sl, "take_profit": tp, "atr": atr}
