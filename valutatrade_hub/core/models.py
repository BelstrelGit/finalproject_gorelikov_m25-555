

from typing import Optional, Dict
# import time
import hashlib
from typing import Optional


def _utc_iso_now() -> str:
    """Текущее время в UTC как ISO-строка: YYYY-MM-DDTHH:MM:SS"""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())



class User:
    """
    Пользователь системы.

    Приватные атрибуты:
      _user_id: int
      _username: str
      _hashed_password: str
      _salt: str
      _registration_date: str  # ISO-строка (UTC), например '2025-10-09T12:00:00'

    Методы:
      get_user_info() -> dict                      # без пароля
      change_password(new_password: str) -> None   # хеширует и сохраняет пароль
      verify_password(password: str) -> bool       # проверка введённого пароля
    """
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: str,
        ) -> None:
        self._user_id = int(user_id)
        self.username = username
        self._hashed_password = str(hashed_password)
        self._salt = str(salt)
        # если пришло пусто/None — ставим текущее UTC-время в ISO
        self._registration_date = (
            registration_date if registration_date else _utc_iso_now()
        )

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> str:
        # ISO-строка вида 'YYYY-MM-DDTHH:MM:SS'
        return self._registration_date


    def get_user_info(self) -> dict:
        """Вернуть публичную информацию о пользователе (без пароля)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date,
        }

    def change_password(self, new_password: str) -> None:
        """Хешируем пароль как sha256(new_password + salt)."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        payload = (new_password + self._salt).encode("utf-8")
        self._hashed_password = hashlib.sha256(payload).hexdigest()

    def verify_password(self, password: str) -> bool:
        payload = (password + self._salt).encode("utf-8")
        return hashlib.sha256(payload).hexdigest() == self._hashed_password


    def to_dict(self) -> dict:
        """Словарь для JSON (формат как в задании)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "hashed_password": self.hashed_password,
            "salt": self.salt,
            "registration_date": self.registration_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        """Создать User из словаря JSON-формата (как в users.json)."""
        return cls(
            user_id=int(d["user_id"]),
            username=str(d["username"]),
            hashed_password=str(d["hashed_password"]),
            salt=str(d["salt"]),
            registration_date=str(d.get("registration_date") or _utc_iso_now()),
        )



class Wallet:
    """
    Кошелёк для одной валюты.

    Атрибуты:
      currency_code: str  # публичный код валюты (например, "USD", "BTC"), хранится в UPPER
      _balance: float     # приватный баланс (>= 0)

    Методы:
      deposit(amount: float)  -> None
      withdraw(amount: float) -> None
      get_balance_info()      -> dict

    Свойства:
      balance (property): геттер/сеттер с валидацией (>= 0 и число)
    """

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        # валидируем код валюты и приводим к верхнему регистру
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("currency_code должен быть непустой строкой")
        self.currency_code = currency_code.strip().upper()

        # баланс храним в приватном поле; установка через setter для проверки
        self._balance = 0.0
        self.balance = balance

    # ------- property balance -------
    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        try:
            v = float(value)
        except Exception:
            raise ValueError("balance должен быть числом")
        if v < 0:
            raise ValueError("balance не может быть отрицательным")
        self._balance = v

    def deposit(self, amount: float) -> None:
        """Пополнить баланс на положительную сумму."""
        a = self._ensure_positive_amount(amount)
        self._balance += a

    def withdraw(self, amount: float) -> None:
        """Снять средства; сумма не должна превышать текущий баланс."""
        a = self._ensure_positive_amount(amount)
        if a > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance:.4f} {self.currency_code}, требуется {a:.4f}"
            )
        self._balance -= a

    def get_balance_info(self) -> dict:
        """Информация о балансе для вывода/JSON."""
        return {"currency_code": self.currency_code, "balance": self.balance}

    def to_dict(self) -> dict:
        """Словарь для хранения в JSON."""
        return {"currency_code": self.currency_code, "balance": self.balance}

    @classmethod
    def from_dict(cls, d: dict) -> "Wallet":
        """Создать Wallet из словаря вида {'currency_code': 'BTC', 'balance': 0.05}."""
        if "currency_code" not in d:
            raise ValueError("Ожидалось поле 'currency_code' для Wallet")
        return cls(currency_code=d["currency_code"], balance=float(d.get("balance", 0.0)))

    @staticmethod
    def _ensure_positive_amount(amount: float) -> float:
        try:
            a = float(amount)
        except Exception:
            raise ValueError("amount должен быть числом")
        if a <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        return a


class Portfolio:

    """
    Управление кошельками одного пользователя.

    Приватные атрибуты:
      _user_id: int
      _wallets: dict[str, Wallet]   # ключ — код валюты (UPPER), значение — объект Wallet
      _user: User | None            # объект пользователя (опционально; не сериализуется)

    Методы:
      add_currency(currency_code: str) -> Wallet
      get_wallet(currency_code: str) -> Wallet | None
      get_total_value(base_currency='USD', exchange_rates: dict[str, float] | None = None) -> float

    Свойства:
      user_id (read-only)
      user    (read-only; может быть None)
      wallets (read-only; возвращает копию словаря)
    """

    def __init__(
            self,
            user_id: int,
            wallets: Optional[Dict[str, "Wallet"]] = None,
            user: Optional["User"] = None,
    ) -> None:
        self._user_id = int(user_id)
        self._wallets: dict[str, Wallet] = {}
        if wallets:
            for code, w in wallets.items():
                self._wallets[self._ensure_currency(code)] = w
        self._user = user  # объект User не сериализуем в JSON

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def user(self) -> "User | None":
        return self._user  # read-only

    @property
    def wallets(self) -> dict[str, "Wallet"]:
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> "Wallet":
        code = self._ensure_currency(currency_code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже существует")
        w = Wallet(code, 0.0)
        self._wallets[code] = w
        return w

    def get_wallet(self, currency_code: str) -> "Wallet | None":
        return self._wallets.get(self._ensure_currency(currency_code))

    def get_total_value(self, base_currency: str = "USD", exchange_rates: dict[str, float] | None = None) -> float:
        """
        Возвращает суммарную стоимость всех валют в базовой валюте.
        - Если base == code, берём баланс как есть.
        - Иначе ищем курс в exchange_rates по ключу 'CODE_BASE'.
          Если его нет, пробуем обратный курс 'BASE_CODE' (берём 1 / rate).
          Если курса нет вовсе — бросаем ошибку.
        """
        base = self._ensure_currency(base_currency)
        total = 0.0
        for code, w in self._wallets.items():
            if code == base:
                total += w.balance
            else:
                if not exchange_rates:
                    raise ValueError("Не заданы курсы exchange_rates для конвертации")
                key = f"{code}_{base}"
                if key in exchange_rates:
                    rate = float(exchange_rates[key])
                else:
                    inv = f"{base}_{code}"
                    if inv in exchange_rates and float(exchange_rates[inv]) != 0.0:
                        rate = 1.0 / float(exchange_rates[inv])
                    else:
                        raise ValueError(f"Нет курса для пары {code}→{base}")
                total += w.balance * rate
        return total

    def to_dict(self) -> dict:
        """
        Формат, с ТЗ (без поля currency_code внутри):
        {
          "user_id": 1,
          "wallets": {
            "USD": {"balance": 1500.0},
            "BTC": {"balance": 0.05}
          }
        }
        """
        return {
            "user_id": self.user_id,
            "wallets": {code: {"balance": w.balance} for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        """
        Принимает оба формата кошелька:
          - краткий: {"wallets": {"BTC": {"balance": 0.05}, ...}}
          - полный:  {"wallets": {"BTC": {"currency_code": "BTC", "balance": 0.05}, ...}}
        """
        wallets: dict[str, Wallet] = {}
        raw = d.get("wallets", {}) or {}
        for code, wd in raw.items():
            code_up = str(code).upper()
            if "currency_code" in wd:
                wallets[code_up] = Wallet.from_dict(wd)
            else:
                wallets[code_up] = Wallet(code_up, float(wd.get("balance", 0.0)))
        return cls(user_id=int(d["user_id"]), wallets=wallets, user=None)

    @staticmethod
    def _ensure_currency(code: str) -> str:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("currency_code должен быть непустой строкой")
        return code.strip().upper()


