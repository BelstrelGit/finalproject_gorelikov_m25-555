

from __future__ import annotations

import time
from typing import Dict, List

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import BaseApiClient


def _utc_iso_now() -> str:
    # Только stdlib: ISO без таймзоны, UTC
    return  time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


class RatesUpdater:
    """
    Координатор обновления курсов.

    Ожидает:
      - clients: список инстансов, реализующих BaseApiClient (fetch_rates() -> Dict[str, float])
      - storage: объект с методом write_rates_snapshot(latest: dict) -> None
                 (он сохранит итоговый JSON в data/rates.json)

    Поведение:
      - опрашивает клиентов по очереди;
      - логирует успех/ошибку каждого клиента;
      - объединяет словари пар { "BTC_USD": 59337.21, ... };
      - формирует формат Core Service:
            {
              "BTC_USD": {"rate": 59337.21, "updated_at": "<ISO>"},
              "EUR_USD": {"rate": 0.927,    "updated_at": "<ISO>"},
              "source": "ParserService",
              "last_refresh": "<ISO>"
            }
      - при падении одного клиента продолжает с остальными;
      - если не удалось получить ни одного курса — бросает ApiRequestError.
    """ # noqa: E501

    def __init__(self, api_clients: List[BaseApiClient], storage) -> None:
        self._api_clients = list(api_clients)
        self._storage = storage
        self._log = get_logger()

    # valutatrade_hub/parser_service/updater.py
    # убедись, что импортированы time и json, а _utc_iso_now доступен (как у тебя было)

    def run_update(self) -> dict:
        self._log.info("RatesUpdater: start update")

        # 1) читаем текущий snapshot, чтобы не потерять пары от других источников
        prev_snapshot = {}
        try:
            prev_snapshot = self._storage.read_rates_snapshot() or {}
        except Exception as e:
            self._log.error(f"RatesUpdater: read previous snapshot failed: {e}")
            prev_snapshot = {}

        # вытаскиваем прошлые пары в формате { "PAIR": {"rate": ..., "updated_at": ...}, ... } # noqa: E501
        prev_pairs = {}
        if isinstance(prev_snapshot, dict):
            for k, v in prev_snapshot.items():
                if isinstance(v, dict) and "rate" in v:
                    prev_pairs[k] = {
                        "rate": float(v.get("rate", 0.0)),
                        "updated_at": str(v.get("updated_at", "")),
                    }

        # 2) собираем новые пары из всех клиентов
        new_flat: Dict[str, float] = {}
        any_success = False

        for a_client in self._api_clients:
            cname = a_client.__class__.__name__
            try:
                self._log.info(f"RatesUpdater: fetching from {cname} ...")
                data = a_client.fetch_rates()  # -> Dict[str, float]
                if not isinstance(data, dict):
                    raise ApiRequestError(f"{cname} вернул некорректный тип ответа")

                # добавляем в общий плоский словарь новых значений
                for k, v in data.items():
                    try:
                        new_flat[k] = float(v)
                    except Exception:
                        pass

                self._log.info(f"RatesUpdater: {cname} OK ({len(data)} пар)")
                any_success = any_success or bool(data)
            except ApiRequestError as e:
                self._log.error(f"RatesUpdater: {cname} ERROR: {e}")
            except Exception as e:
                self._log.error(f"RatesUpdater: {cname} UNEXPECTED ERROR: {e}")

        # если ни один клиент не дал данных — не трогаем файл и отдаём ошибку
        if not any_success or not new_flat:
            msg = "Не удалось получить курсы ни от одного источника"
            self._log.error(f"RatesUpdater: FAILED — {msg}")
            raise ApiRequestError(msg)

        now_iso = _utc_iso_now()
        now_epoch = int(time.time())

        # 3) формируем итоговый snapshot:
        #    - старые пары переносим как есть
        #    - новые пары перезаписывают старые и получают свежий updated_at
        latest: dict = {}

        # сначала — все старые пары
        for k, rec in prev_pairs.items():
            latest[k] = {
                "rate": float(rec.get("rate", 0.0)),
                "updated_at": str(rec.get("updated_at", "")),
            }

        # затем — новые пары (перезапишут при совпадении ключа)
        for k, rate in new_flat.items():
            latest[k] = {"rate": float(rate), "updated_at": now_iso}

        # метаданные
        latest["source"] = "ParserService"
        latest["last_refresh"] = now_iso
        latest["last_refresh_epoch"] = now_epoch

        # 4) сохраняем
        try:
            self._storage.write_rates_snapshot(latest)
            self._log.info(
                f"RatesUpdater: snapshot saved ({len(new_flat)} новых пар), last_refresh={now_iso}" # noqa: E501
            )
        except Exception as e:
            self._log.error(f"RatesUpdater: storage write failed: {e}")
            raise

        self._log.info("RatesUpdater: done")
        return latest
