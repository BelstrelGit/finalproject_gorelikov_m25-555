from __future__ import annotations

import json
import os
import time
from typing import Any

from valutatrade_hub.parser_service.config import ParserConfig


def _utc_iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


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

    # ---------- internal helpers ----------
    def _ensure_parent_dir(self, path: str) -> None:
        dir = os.path.dirname(path)
        if dir and not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)

    def _read_json_or(self, path: str, default: Any) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    # ---------- public API ----------
    def write_rates_snapshot(self, latest: dict) -> None:
        """
        Перезаписать актуальный снапшот (rates.json) и одновременно
        добавить запись в историю (exchange_rates.json).
        """
        # 1) Снапшот
        snap_path = self._cfg.RATES_FILE_PATH
        self._ensure_parent_dir(snap_path)
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(latest, f, ensure_ascii=False, indent=2, sort_keys=True)

        # 2) История (append)
        self.append_history(latest)

    def append_history(self, latest: dict) -> None:
        """
        Добавить запись в историю (список) в exchange_rates.json.
        """
        hist_path = self._cfg.HISTORY_FILE_PATH
        self._ensure_parent_dir(hist_path)

        history = self._read_json_or(hist_path, default=[])
        if not isinstance(history, list):
            history = []

        record = {
            "ts": str(latest.get("last_refresh") or _utc_iso_now()),
            "source": str(latest.get("source", "ParserService")),
            "pairs": {k: v for k, v in latest.items() if isinstance(v, dict) and "rate" in v}, # noqa: E501
        }
        history.append(record)

        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    # (по желанию) утилиты чтения TODO CHECK OR DELETE!
    def load_snapshot(self) -> dict:
        return self._read_json_or(self._cfg.RATES_FILE_PATH, default={})

    def load_history(self) -> list:
        return self._read_json_or(self._cfg.HISTORY_FILE_PATH, default=[])

    def read_rates_snapshot(self) -> dict:
        """Вернёт текущий snapshot из RATES_FILE_PATH или {}."""
        return self._read_json_or(self._cfg.RATES_FILE_PATH, default={})
