import ccxt
import pandas as pd
import logging

logger = logging.getLogger("trading_bot")


class ExchangeConnector:
    """Unified exchange interface via CCXT with Bybit-specific handling."""

    def __init__(self, config: dict):
        exchange_cfg = config["exchange"]
        exchange_name = exchange_cfg.get("name", "bybit")

        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{exchange_name}' not supported by ccxt")

        params = {
            "enableRateLimit": True,
        }

        api_key = exchange_cfg.get("api_key", "")
        api_secret = exchange_cfg.get("api_secret", "")
        if api_key and api_key != "your_bybit_api_key_here":
            params["apiKey"] = api_key
            params["secret"] = api_secret

        if exchange_cfg.get("password"):
            params["password"] = exchange_cfg["password"]

        # Bybit-specific: default to spot market
        if exchange_name == "bybit":
            params["options"] = {
                "defaultType": "spot",
            }

        self.exchange = exchange_class(params)

        if exchange_cfg.get("sandbox", False):
            if hasattr(self.exchange, "set_sandbox_mode"):
                self.exchange.set_sandbox_mode(True)
                logger.info("Sandbox/testnet mode enabled")

        self.exchange.load_markets()
        logger.info(f"Connected to {exchange_name} ({len(self.exchange.markets)} markets)")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def create_market_buy(self, symbol: str, amount: float) -> dict:
        logger.info(f"MARKET BUY  {amount} {symbol}")
        return self.exchange.create_market_buy_order(symbol, amount)

    def create_market_sell(self, symbol: str, amount: float) -> dict:
        logger.info(f"MARKET SELL {amount} {symbol}")
        return self.exchange.create_market_sell_order(symbol, amount)

    def create_limit_buy(self, symbol: str, amount: float, price: float) -> dict:
        logger.info(f"LIMIT BUY  {amount} {symbol} @ {price}")
        return self.exchange.create_limit_buy_order(symbol, amount, price)

    def create_limit_sell(self, symbol: str, amount: float, price: float) -> dict:
        logger.info(f"LIMIT SELL {amount} {symbol} @ {price}")
        return self.exchange.create_limit_sell_order(symbol, amount, price)
