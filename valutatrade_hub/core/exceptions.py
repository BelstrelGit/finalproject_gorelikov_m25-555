


# class CurrencyNotFoundError(Exception):
#     """Запрошенный валютный код не найден в реестре."""
#     pass

class InsufficientFundsError(Exception):
    """Недостаточно средств: доступно {available} {code}, требуется {required} {code}"""

    def __init__(self, available: float, required: float, code: str):
        self.available = float(available)
        self.required = float(required)
        self.code = str(code).upper()
        msg = (
            f"Недостаточно средств: доступно {self.available:.4f} {self.code}, "
            f"требуется {self.required:.4f} {self.code}"
        )
        super().__init__(msg)


class CurrencyNotFoundError(Exception):
    """Неизвестная валюта '{code}'"""

    def __init__(self, code: str):
        self.code = str(code).upper() if isinstance(code, str) else str(code)
        super().__init__(f"Неизвестная валюта '{self.code}'")


class ApiRequestError(Exception):
    """Ошибка при обращении к внешнему API: {reason}"""

    def __init__(self, reason: str):
        self.reason = str(reason)
        super().__init__(f"Ошибка при обращении к внешнему API: {self.reason}")

