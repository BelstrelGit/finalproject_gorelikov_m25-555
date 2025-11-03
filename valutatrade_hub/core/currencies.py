



from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency:
    """
    Абстрактный базовый класс валюты (без импорта abc).
    Публичные атрибуты:
      - name: читаемое имя ("US Dollar", "Bitcoin")
      - code: код в верхнем регистре ("USD", "EUR", "BTC", "ETH"), 2..5 символов
    Обязательный метод:
      - get_display_info() -> str
    """

    def __init__(self, name: str, code: str) -> None:
        # name — непустая строка
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name должен быть непустой строкой")
        # code — верхний регистр, длина 2..5, без пробелов
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code должен быть непустой строкой")
        c = code.strip().upper()
        if " " in c or not (2 <= len(c) <= 5):
            raise ValueError("code: верхний регистр, длина 2..5, без пробелов")

        self.name = name.strip()
        self.code = c

    # “абстрактный” метод
    def get_display_info(self) -> str:
        raise NotImplementedError("Currency.get_display_info должен быть переопределён")

    def __repr__(self) -> str:
        return f"<Currency code={self.code} name={self.name}>"


class FiatCurrency(Currency):
    """
    Фиатная валюта.
    Доп. атрибут:
      - issuing_country: страна/зона эмиссии ("United States", "Eurozone")
    """

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("issuing_country должен быть непустой строкой")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        # Пример формата: [FIAT] USD — US Dollar (Issuing: United States)
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """
    Криптовалюта.
    Доп. атрибуты:
      - algorithm: строка (например, "SHA-256", "Ethash")
      - market_cap: float >= 0 (последняя известная капитализация)
    """

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0) -> None:
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("algorithm должен быть непустой строкой")
        try:
            mc = float(market_cap)
        except Exception:
            raise ValueError("market_cap должен быть числом")
        if mc < 0:
            raise ValueError("market_cap не может быть отрицательным")

        self.algorithm = algorithm.strip()
        self.market_cap = mc

    def _fmt_mcap(self) -> str:
        # Краткая научная форма, как в примере: 1.12e12
        return f"{self.market_cap:.2e}"

    def get_display_info(self) -> str:
        # Пример: [CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self._fmt_mcap()})"


# ---------- реестр / фабрика ----------

# Базовый предзаполненный реестр (можно расширять register_currency)
_REGISTRY = {
    "USD": FiatCurrency(name="US Dollar", code="USD", issuing_country="United States"),
    "EUR": FiatCurrency(name="Euro", code="EUR", issuing_country="Eurozone"),
    "BTC": CryptoCurrency(name="Bitcoin", code="BTC", algorithm="SHA-256", market_cap=1.12e12),
    "ETH": CryptoCurrency(name="Ethereum", code="ETH", algorithm="Ethash", market_cap=4.50e11),
    # при желании добавляй RUB, GBP, USDT и т.д.
}


def register_currency(currency: Currency) -> None:
    """
    Зарегистрировать или перезаписать валюту в реестре.
    """
    if not isinstance(currency, Currency):
        raise ValueError("Можно регистрировать только объекты Currency")
    _REGISTRY[currency.code] = currency


def get_currency(code: str) -> Currency:
    """
    Фабрика валют: вернуть объект Currency по коду.
    Если код неизвестен — CurrencyNotFoundError.
    """
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError("Пустой валютный код")
    c = code.strip().upper()
    cur = _REGISTRY.get(c)
    if cur is None:
        raise CurrencyNotFoundError(f"Валюта '{c}' не найдена")
    return cur
