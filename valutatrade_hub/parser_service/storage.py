
from __future__ import annotations

from typing import Any, Dict

from valutatrade_hub.core.utils import read_json, write_json
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """
    Хранилище для Parser Service.

    - Сохраняет актуальный снапшот в cfg.RATES_FILE_PATH (его читает Core Service).
    - Ведёт историю обновлений в cfg.HISTORY_FILE_PATH (список записей).

    Формат снапшота (ожидается Core Service):
    {
      "BTC_USD": {"rate": 59337.21, "updated_at": "2025-10-09T10:29:42"},
      "EUR_USD": {"rate": 0.927,    "updated_at": "2025-10-09T10:30:00"},
      "source": "ParserService",
      "last_refresh": "2025-10-09T10:35:00"
    }

    Формат истории (список):
    [
      {
        "ts": "2025-10-09T10:35:00",
        "source": "ParserService",
        "pairs": {
          "BTC_USD": {"rate": 59337.21, "updated_at": "2025-10-09T10:29:42"},
          "EUR_USD": {"rate": 0.927,    "updated_at": "2025-10-09T10:30:00"}
        }
      },
      ...
    ]
    """

    def __init__(self, cfg: ParserConfig | None = None) -> None:
        self._cfg = cfg or ParserConfig()

    def write_rates_snapshot(self, latest: Dict[str, Any]) -> None:
        """
        Сохраняет актуальный снапшот (атомарно) и добавляет его в историю.
        Формат latest: {"PAIR": {"rate": float, "updated_at": str},
        "source": ..., "last_refresh": ...}
        """
        # актуальный снапшот для Core
        write_json(self._cfg.RATES_FILE_PATH, latest, atomic=True)

        # история Parser Service
        history = read_json(self._cfg.HISTORY_FILE_PATH, default=[])
        if not isinstance(history, list):
            history = []
        history.append(latest)
        write_json(self._cfg.HISTORY_FILE_PATH, history, atomic=True)

    def read_latest_snapshot(self) -> Dict[str, Any]:
        """Вернёт последний актуальный снапшот из кеша (или пустой dict)."""
        snap = read_json(self._cfg.RATES_FILE_PATH, default={})
        return snap if isinstance(snap, dict) else {}
