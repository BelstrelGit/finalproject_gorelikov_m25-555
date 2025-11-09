from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Dict, List

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

# ------------------ Абстракция клиента ------------------

class BaseApiClient(ABC):
    """Базовый интерфейс клиента внешнего API."""

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """
        Вернуть курсы в стандартизованном формате:
        {
          "BTC_USD": 59337.21,
          "ETH_USD": 3720.00,
          "EUR_USD": 0.927,
          ...
        }
        """
        pass


# ------------------ CoinGecko (криптовалюты) ------------------

class CoinGeckoClient(BaseApiClient):
    """
    Формирует запрос:
      GET {COINGECKO_URL}?ids=<id1,id2,...>&vs_currencies=<vs>
    где ids берём из CRYPTO_ID_MAP по кодам CRYPTO_CURRENCIES.
    """

    def __init__(self, codes: List[str] | None = None,
                 vs_currency: str | None = None,
                 cfg: ParserConfig | None = None):
        self._cfg = cfg or ParserConfig()
        # список кодов для запроса (по умолчанию из конфига)
        self._codes = [c.upper() for c in (codes or list(self._cfg.CRYPTO_CURRENCIES))]
        # базовая валюта для котировок (CoinGecko ждёт в нижнем регистре)
        self._quote_currency = (vs_currency or self._cfg.BASE_FIAT_CURRENCY).lower()

    def fetch_rates(self) -> Dict[str, float]:
        # собрать ids по маппингу
        ids: List[str] = []
        for code in self._codes:
            coin_id = self._cfg.CRYPTO_ID_MAP.get(code)
            if coin_id:
                ids.append(coin_id)
        if not ids:
            return {}

        query = urllib.parse.urlencode({
            "ids": ",".join(ids),
            "vs_currencies": self._quote_currency,
        })

        url = f"{self._cfg.COINGECKO_URL}?{query}"
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ValutaTradeHub/1.0 (stdlib-urllib)")
            with urllib.request.urlopen(req, timeout=self._cfg.REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    # например, 429 Too Many Requests
                    raise ApiRequestError(f"CoinGecko HTTP {resp.status}")
                raw = resp.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise ApiRequestError(f"Ошибка сети CoinGecko: {e}") from e
        except Exception as e:
            raise ApiRequestError(f"Ошибка при запросе CoinGecko: {e}") from e

        try:
            data = json.loads(raw)  # {"bitcoin":{"usd":...}, "ethereum":{"usd":...}, ...} # noqa: E501
        except Exception as e:
            raise ApiRequestError(f"Невалидный JSON от CoinGecko: {e}") from e

        # привести к {"BTC_USD": rate, ...}
        out: Dict[str, float] = {}
        for code in self._codes:
            coin_id = self._cfg.CRYPTO_ID_MAP.get(code)
            try:
                rate = float(data[coin_id][self._quote_currency])
                out[f"{code}_{self._quote_currency.upper()}"] = rate
            except Exception:
                # если в ответе нет монеты/поля — пропускаем
                pass

        return out


# ------------------ ExchangeRate-API (фиатные валюты) ------------------

class ExchangeRateApiClient(BaseApiClient):
    """
    Формирует запрос:
      GET {EXCHANGERATE_API_URL}/{API_KEY}/latest/{BASE}
    Извлекает курсы из поля "rates" и возвращает пары { "<CODE>_<BASE>": rate }.
    """

    def __init__(self, base: str | None = None,
                 codes: List[str] | None = None,
                 cfg: ParserConfig | None = None):
        self._cfg = cfg or ParserConfig()
        self._base = (base or self._cfg.BASE_FIAT_CURRENCY).upper()
        self._codes = [c.upper() for c in (codes or list(self._cfg.FIAT_CURRENCIES))]


    def fetch_rates(self) -> Dict[str, float]:
        api_key = (self._cfg.EXCHANGERATE_API_KEY or "").strip()
        if not api_key:
            raise ApiRequestError("Не задан EXCHANGERATE_API_KEY для ExchangeRate-API")

        url = f"{self._cfg.EXCHANGERATE_API_URL}/{api_key}/latest/{self._base}"

        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ValutaTradeHub/1.0 (stdlib-urllib)")
            with urllib.request.urlopen(req, timeout=self._cfg.REQUEST_TIMEOUT) as resp:
                status = getattr(resp, "status", None)
                if status is None:
                    status = resp.getcode()
                if status != 200:
                    # 401 — неверный ключ, 429 — лимит, 5xx — недоступность и т.п.
                    raise ApiRequestError(f"ExchangeRate-API HTTP {status}")
                raw = resp.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise ApiRequestError(f"Ошибка сети ExchangeRate-API: {e}") from e
        except Exception as e:
            raise ApiRequestError(f"Ошибка при запросе ExchangeRate-API: {e}") from e

        try:
            data = json.loads(raw)
        except Exception as e:
            raise ApiRequestError(f"Невалидный JSON от ExchangeRate-API: {e}") from e

        # проверка статуса API
        if not isinstance(data, dict) or str(data.get("result", "")).lower() != "success": # noqa: E501
            msg = data.get("error-type") if isinstance(data, dict) else "unknown error"
            raise ApiRequestError(f"ExchangeRate-API ответ: {msg}")

        # ВАЖНО: у v6 часто 'conversion_rates'
        rates = data.get("rates") or data.get("conversion_rates")
        if not isinstance(rates, dict):
            raise ApiRequestError("ExchangeRate-API: отсутствуют 'rates'/'conversion_rates' в ответе") # noqa: E501

        out: Dict[str, float] = {}
        for code in self._codes:
            if code == self._base:
                # можно оставить пропуск; при желании можно писать 1.0
                continue
            try:
                out[f"{code}_{self._base}"] = float(rates[code])
            except Exception:
                # нет такого кода в ответе — пропускаем
                pass

        if not out:
            raise ApiRequestError(
                f"ExchangeRate-API: ни одного курса из {self._codes} для базы {self._base}" # noqa: E501
            )

        return out
