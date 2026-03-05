from .sma_crossover import SmaCrossoverStrategy
from .rsi_strategy import RsiStrategy
from .macd_strategy import MacdStrategy
from .bollinger_strategy import BollingerStrategy
from .alpha_composite import AlphaCompositeStrategy

STRATEGIES = {
    "sma_crossover": SmaCrossoverStrategy,
    "rsi": RsiStrategy,
    "macd": MacdStrategy,
    "bollinger": BollingerStrategy,
    "alpha_composite": AlphaCompositeStrategy,
}


def get_strategy(name: str, params: dict):
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(STRATEGIES.keys())}")
    return STRATEGIES[name](params)
