import os
import yaml
from dotenv import load_dotenv


def load_config(config_path: str = "config.yaml") -> dict:
    load_dotenv()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    config.setdefault("exchange", {})
    config["exchange"]["api_key"] = os.getenv("EXCHANGE_API_KEY", "")
    config["exchange"]["api_secret"] = os.getenv("EXCHANGE_API_SECRET", "")
    config["exchange"]["password"] = os.getenv("EXCHANGE_PASSWORD", "")

    return config
