
from __future__ import annotations

import hashlib
import secrets
from typing import Tuple

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
)
from valutatrade_hub.core.utils import (
    flatten_rates_snapshot as _flatten_rates_snapshot,
)
from valutatrade_hub.core.utils import (
    fmt_amount as _fmt_amount,
)
from valutatrade_hub.core.utils import (
    is_cache_fresh as _is_cache_fresh,
)
from valutatrade_hub.core.utils import (
    normalize_currency_code as _cur,
)
from valutatrade_hub.core.utils import (
    parse_positive_amount as _pos_amount,
)
from valutatrade_hub.core.utils import (
    rate_from_flat as _rate_from_flat,
)
from valutatrade_hub.core.utils import read_json as _load_json
from valutatrade_hub.core.utils import (
    utc_iso_now as _utc_iso_now,
)
from valutatrade_hub.core.utils import write_json as _save_json
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader

# -------------------- SETTINGS & PATHS --------------------

_settings = SettingsLoader()

USERS_PATH = _settings.get("USERS_PATH", "data/users.json")
PORTFOLIOS_PATH = _settings.get("PORTFOLIOS_PATH", "data/portfolios.json")
SESSION_PATH = _settings.get("SESSION_PATH", "data/session.json")
RATES_PATH = _settings.get("RATES_PATH", "data/rates.json")

_DEFAULT_BASE = _settings.get("DEFAULT_BASE_CURRENCY", "USD")


# -------------------- USERS --------------------

def _find_user_by_username(username: str) -> dict | None:
    users = _load_json(USERS_PATH, [])
    for u in users:
        if u.get("username") == username:
            return u
    return None


def _next_user_id() -> int:
    users = _load_json(USERS_PATH, [])
    max_id = 0
    for u in users:
        try:
            uid = int(u.get("user_id", 0))
            if uid > max_id:
                max_id = uid
        except Exception:
            pass
    return max_id + 1


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# -------------------- SESSION --------------------

def _get_session() -> dict:
    s = _load_json(SESSION_PATH, {})
    if isinstance(s, dict) and "user_id" in s and "username" in s:
        return s
    return {}


def _require_session() -> dict:
    s = _get_session()
    if not s:
        raise ValueError("Сначала выполните login")
    return s


# -------------------- PORTFOLIOS --------------------

def _load_user_portfolio(user_id: int) -> dict:
    """
    Возвращает {"USD": {"balance": 0.0}, ...} либо {}.
    """
    ports = _load_json(PORTFOLIOS_PATH, [])
    for p in ports:
        try:
            if int(p.get("user_id")) == int(user_id):
                return dict(p.get("wallets", {}) or {})
        except Exception:
            pass
    return {}


def _save_user_portfolio(user_id: int, wallets: dict) -> None:
    ports = _load_json(PORTFOLIOS_PATH, [])
    updated = False
    for p in ports:
        try:
            if int(p.get("user_id")) == int(user_id):
                p["wallets"] = wallets
                updated = True
                break
        except Exception:
            pass
    if not updated:
        ports.append({"user_id": int(user_id), "wallets": wallets})
    _save_json(PORTFOLIOS_PATH, ports)


# -------------------- RATES --------------------

def _read_rates_snapshot() -> dict:
    return _load_json(RATES_PATH, {})


def _cache_is_fresh(ttl_sec: int) -> bool:
    """
    Использует как epoch-маркер (last_refresh_epoch), так и ISO (last_refresh).
    """
    snapshot = _read_rates_snapshot()
    return _is_cache_fresh(snapshot, ttl_sec)


def _get_rate_pair(frm: str, to: str) -> Tuple[float, str]:
    """
    Возвращает (rate, updated_at_str) для пары frm→to.
    Берёт курс из RATES_PATH, при отсутствии прямой пары — инвертирует обратную.
    """
    snapshot = _read_rates_snapshot()
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError(f"Курс {frm}→{to} недоступен. Повторите попытку позже.")
    flat = _flatten_rates_snapshot(snapshot)

    # курс
    rate = _rate_from_flat(frm, to, flat)

    # метка времени для пары — из direct или inverse записи
    f = frm.strip().upper()
    t = to.strip().upper()
    direct = snapshot.get(f"{f}_{t}")
    if isinstance(direct, dict) and "updated_at" in direct:
        return float(rate), str(direct["updated_at"])
    inv = snapshot.get(f"{t}_{f}")
    if isinstance(inv, dict) and "updated_at" in inv:
        return float(rate), str(inv["updated_at"])
    return float(rate), ""


# -------------------- PUBLIC USECASES --------------------

@log_action("REGISTER")
def register(username: str, password: str) -> str:
    username = (username or "").strip()
    if not username:
        raise ValueError("Имя пользователя не должно быть пустым")

    if _find_user_by_username(username):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    user_id = _next_user_id()
    salt = secrets.token_hex(16)
    hashed = _hash_password(password, salt)

    users = _load_json(USERS_PATH, [])
    users.append(
        {
            "user_id": user_id,
            "username": username,
            "hashed_password": hashed,
            "salt": salt,
            "registration_date": _utc_iso_now(),
        }
    )
    _save_json(USERS_PATH, users)
    return f"Пользователь '{username}' зарегистрирован"


@log_action("LOGIN")
def login(username: str, password: str) -> str:
    username = (username or "").strip()
    u = _find_user_by_username(username)
    if not u:
        raise ValueError(f"Пользователь '{username}' не найден")

    salt = str(u.get("salt", ""))
    hashed = str(u.get("hashed_password", ""))
    if _hash_password(password, salt) != hashed:
        raise ValueError("Неверный пароль")

    sess = {"user_id": int(u["user_id"]), "username": username}
    _save_json(SESSION_PATH, sess)
    return f"Вы вошли как '{username}'"


def show_portfolio(base_currency: str = _DEFAULT_BASE) -> str:
    sess = _require_session()
    user_id = int(sess["user_id"])
    username = str(sess["username"])

    wallets = _load_user_portfolio(user_id)
    if not wallets:
        return "У вас пока нет кошельков. Добавьте валюту покупкой (команда buy)."

    base = _cur(base_currency)
    # валидируем код базы через реестр
    get_currency(base)

    snapshot = _read_rates_snapshot()
    flat = _flatten_rates_snapshot(snapshot)

    lines = [f"Портфель пользователя '{username}' (база: {base}):"]
    total = 0.0

    for code in sorted(wallets.keys()):
        code_u = _cur(code)
        try:
            bal = float(wallets[code].get("balance", 0.0))
        except Exception:
            bal = 0.0

        try:
            rate = _rate_from_flat(code_u, base, flat)
        except Exception:
            # если курса нет — даём понятную ошибку
            raise ValueError(f"Нет курса для пары {code_u}→{base}")

        val_in_base = bal * rate
        total += val_in_base
        lines.append(f"- {code_u}: {_fmt_amount(bal)}  → {val_in_base:.2f} {base}")

    lines.append("---------------------------------")
    lines.append(f"ИТОГО: {total:,.2f} {base}")
    return "\n".join(lines)


@log_action("BUY", verbose=True)
def buy(currency: str, amount) -> str:
    """
    Покупка currency за USD:
      - проверка логина,
      - валидируем валюту (реестр) и amount > 0,
      - списываем USD, начисляем currency,
      - используем курс currency→USD из локального кэша для оценочной стоимости.
    """
    sess = _require_session()
    user_id = int(sess["user_id"])

    code = _cur(currency)
    get_currency(code)  # может бросить CurrencyNotFoundError

    amt = _pos_amount(amount)

    wallets = _load_user_portfolio(user_id)
    prev = float(wallets.get(code, {}).get("balance", 0.0))

    # курс currency→USD
    try:
        rate, _ts = _get_rate_pair(code, "USD")
    except Exception:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    cost_usd = amt * rate
    usd_prev = float(wallets.get("USD", {}).get("balance", 0.0))
    if usd_prev < cost_usd:
        raise InsufficientFundsError(code="USD", available=usd_prev, required=cost_usd)

    # применяем изменения
    wallets["USD"] = {"balance": usd_prev - cost_usd}
    wallets[code] = {"balance": prev + amt}
    _save_user_portfolio(user_id, wallets)

    return (
        f"Покупка выполнена: {amt:.4f} {code} по курсу {rate:.2f} USD/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {prev:.4f} → стало {prev + amt:.4f}\n"
        f"- USD:  было {usd_prev:.2f} → стало {usd_prev - cost_usd:.2f}\n"
        f"Оценочная стоимость покупки: {cost_usd:.2f} USD"
    )


@log_action("SELL", verbose=True)
def sell(currency: str, amount) -> str:
    """
    Продажа currency за USD:
      - проверка логина,
      - валидируем валюту и amount,
      - проверяем остаток, списываем currency, пополняем USD.
    """
    sess = _require_session()
    user_id = int(sess["user_id"])

    code = _cur(currency)
    if code == "USD":
        raise ValueError("Продажа USD не поддерживается. Укажите другую валюту.")
    get_currency(code)

    amt = _pos_amount(amount)

    wallets = _load_user_portfolio(user_id)
    prev = float(wallets.get(code, {}).get("balance", 0.0))
    if prev < amt:
        raise InsufficientFundsError(code=code, available=prev, required=amt)

    try:
        rate, _ts = _get_rate_pair(code, "USD")
    except Exception:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    revenue_usd = amt * rate
    usd_prev = float(wallets.get("USD", {}).get("balance", 0.0))

    wallets[code] = {"balance": prev - amt}
    wallets["USD"] = {"balance": usd_prev + revenue_usd}
    _save_user_portfolio(user_id, wallets)

    return (
        f"Продажа выполнена: {amt:.4f} {code} по курсу {rate:.2f} USD/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {prev:.4f} → стало {prev - amt:.4f}\n"
        f"- USD:  было {usd_prev:.2f} → стало {usd_prev + revenue_usd:.2f}\n"
        f"Оценочная выручка: {revenue_usd:.2f} USD"
    )


def get_rate(frm: str, to: str) -> str:
    """
    По ТЗ: валидация кодов через реестр; TTL из SettingsLoader;
    при устаревшем кэше — ApiRequestError.
    """
    # политика свежести
    ttl = int(_settings.get("RATES_TTL_SECONDS", 300))
    if not _cache_is_fresh(ttl):
        raise ApiRequestError("Ошибка при обращении к внешнему API: "
                              "данные курсов устарели")

    # валидация валют
    f = _cur(frm)
    t = _cur(to)
    get_currency(f)
    get_currency(t)

    # курс + метка
    rate, ts = _get_rate_pair(f, t)
    back_rate = 1.0 if rate == 0 else (1.0 / rate)
    ts_str = ts if ts else "неизвестно"

    return (
        f"Курс {f}→{t}: {rate:.8f} (обновлено: {ts_str})\n"
        f"Обратный курс {t}→{f}: {back_rate:.5f}"
    )
