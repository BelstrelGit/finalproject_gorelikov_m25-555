

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParserConfig:
    """
    Конфигурация Parser Service.

    Чувствительные данные (EXCHANGERATE_API_KEY) берутся из переменной окружения
    и не хранятся в коде/репозитории.
    """


    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", "").strip()
    )

    # --- Эндпоинты ---
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # --- Списки валют/маппинги ---
    BASE_FIAT_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # --- Пути к файлам ---
    RATES_FILE_PATH: str = "data/rates.json"              # локальный кэш для Core Service # noqa: E501
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"   # хранилище Parser Service (исторические данные).json # noqa: E501

    # --- Параметры запросов ---
    REQUEST_TIMEOUT: int = 10  # секунд
