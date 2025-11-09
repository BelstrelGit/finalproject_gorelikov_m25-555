from __future__ import annotations

import time

from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

_log = get_logger()


_log = get_logger()


def _build_clients(source: str | None, cfg: ParserConfig):
    """
    Собирает RatesUpdater с нужным набором клиентов.
    source: None | 'coingecko' | 'exchangerate'
    """
    s = (source or "").strip().lower()
    if s in ("", "all", None):  # «all» = оба
        return [CoinGeckoClient(cfg=cfg), ExchangeRateApiClient(cfg=cfg)]
    if s == "coingecko":
        return [CoinGeckoClient(cfg=cfg)]
    if s == "exchangerate":
        return [ExchangeRateApiClient(cfg=cfg)]
    # неизвестное значение — безопасно трактуем как «оба»
    return [CoinGeckoClient(cfg=cfg), ExchangeRateApiClient(cfg=cfg)]


def run_scheduler(interval: int, source: str = "all", iterations: int | None = None):
    """
    Периодически запускает обновление курсов.
    interval — пауза между запусками (в секундах).
    source — ограничить источником ('coingecko' | 'exchangerate'), по умолчанию оба.
    iterations — если указано, выполнит указанное число итераций
    и завершится (удобно для тестов).
    """
    cfg = ParserConfig()
    storage = RatesStorage(cfg=cfg)
    clients = _build_clients(source, cfg)

    _log.info(f"Scheduler: start (interval={interval}s, source={source})")
    i = 0
    while iterations is None or i < iterations:
        try:
            RatesUpdater(clients, storage).run_update()
        except Exception as e:
            _log.error(f"Scheduler: update failed: {e}")
        time.sleep(int(interval))
        i += 1
