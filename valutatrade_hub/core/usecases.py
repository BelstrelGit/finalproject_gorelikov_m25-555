# stdlib only
import hashlib
import json
import time

# новенькое
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Wallet
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader

# ДОБАВИТЬ:

# создать singleton (если он уже создан в другом месте, вернётся тот же инстанс)


_settings = SettingsLoader()

USERS_PATH = _settings.get("USERS_PATH", "data/users.json")
PORTFOLIOS_PATH = _settings.get("PORTFOLIOS_PATH", "data/portfolios.json")
SESSION_PATH = _settings.get("SESSION_PATH", "data/session.json")
RATES_PATH = _settings.get("RATES_PATH", "data/rates.json")

_DEFAULT_BASE = _settings.get("DEFAULT_BASE_CURRENCY", "USD")
_RATES_TTL = int(_settings.get("RATES_TTL_SECONDS", 300))


# (опционально) можно использовать дефолтную базовую валюту:
# DEFAULT_BASE = _settings.default_base_currency()

# --- свежесть кэша: epoch -> bool ---
# --- helpers: извлекаем метку времени из snapshot (epoch с фоллбэком на ISO) ---
def _snapshot_epoch(snap: dict) -> int:
    """Возвращает last_refresh_epoch, а при его отсутствии парсит last_refresh (ISO)."""
    try:
        e = int(snap.get("last_refresh_epoch", 0))
        if e > 0:
            return e
    except Exception:
        pass

    ts = str(snap.get("last_refresh", "")).strip()
    if ts:
        # ожидаем формат 'YYYY-MM-DDTHH:MM:SS[...]', берём первые 19 символов
        try:
            t = time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
            return int(time.mktime(t))
        except Exception:
            pass
    return 0


def _rates_are_fresh(snap: dict, ttl_seconds: int) -> bool:
    e = _snapshot_epoch(snap)
    if e <= 0:
        return False
    now = int(time.time())
    return (now - e) <= int(ttl_seconds)


def _cache_is_fresh(ttl_sec: int) -> bool:
    snap = _load_json(RATES_PATH, {})
    try:
        ts = int(snap.get("last_refresh_epoch", 0))
    except Exception:
        ts = 0
    if ts <= 0:
        return False
    now = int(time.time())
    return (now - ts) <= int(ttl_sec)


# ---------- json helpers ----------
def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- time ----------
def _utc_iso_now() -> str:
    # ISO без таймзоны (UTC)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


# ---------- user utils ----------
def _generate_salt(username: str) -> str:
    raw = f"{username}|{time.time_ns()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _find_user_by_username(username: str):
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


# ---------- session ----------
def _get_session() -> dict:
    s = _load_json(SESSION_PATH, {})
    return s if isinstance(s, dict) and "user_id" in s and "username" in s else {}


def _set_session(user_id: int, username: str) -> None:
    _save_json(SESSION_PATH, {"user_id": int(user_id), "username": str(username)})


def _require_session() -> dict:
    s = _get_session()
    if not s:
        raise ValueError("Сначала выполните login")
    return s


# ---------- portfolio I/O ----------
def _load_user_portfolio(user_id: int) -> dict:
    """
    Возвращает dict вида {"USD": {"balance": 1500.0}, "BTC": {"balance": 0.05}, ...}
    Если портфеля нет — вернёт {}.
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


# ---------- rates ----------
def _load_rates_map() -> dict:
    """
    Плоский словарь пар:
      {"EUR_USD": 1.0786, "BTC_USD": 59337.21, ...}
    Игнорирует служебные ключи (source, last_refresh).
    """
    raw = _load_json(RATES_PATH, {})
    flat = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not isinstance(k, str):
                continue
            if k in ("source", "last_refresh"):
                continue
            if isinstance(v, dict) and "rate" in v:
                try:
                    flat[k] = float(v["rate"])
                except Exception:
                    pass
    return flat


def _load_rates_full() -> dict:
    """
    Полный вид с updated_at:
      {"BTC_USD": {"rate": 59337.21, "updated_at": "..."}, ...}
    """
    raw = _load_json(RATES_PATH, {})
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in ("source", "last_refresh"):
                continue
            if isinstance(v, dict) and "rate" in v:
                try:
                    out[k] = {"rate": float(v["rate"]), "updated_at": str(v.get("updated_at", ""))}  # noqa: E501
                except Exception:
                    pass
    return out


def _has_any_rate_for_base(base: str, rates: dict) -> bool:
    base = base.upper()
    for k in rates.keys():
        if k.endswith(f"_{base}") or k.startswith(f"{base}_"):
            return True
    return False


def _get_rate(code: str, base: str, rates: dict) -> float:
    """Для show-portfolio: ищем прямой CODE_BASE, иначе инвертируем BASE_CODE."""
    code = code.upper()
    base = base.upper()
    if code == base:
        return 1.0
    key = f"{code}_{base}"
    if key in rates:
        return float(rates[key])
    inv = f"{base}_{code}"
    if inv in rates and float(rates[inv]) != 0.0:
        return 1.0 / float(rates[inv])
    raise ValueError(f"Нет курса для пары {code}→{base}")


def _get_rate_pair(frm: str, to: str) -> tuple[float, str]:
    """
    Для get-rate/buy/sell: возвращает (rate, updated_at) для frm→to.
    Прямой или обратный (инвертируем).
    """
    frm = frm.strip().upper()
    to = to.strip().upper()
    if not frm or not to:
        raise ValueError("Коды валют должны быть непустыми строками")
    if frm == to:
        return 1.0, _utc_iso_now()

    rates = _load_rates_full()
    k = f"{frm}_{to}"
    if k in rates:
        rec = rates[k]
        return float(rec["rate"]), str(rec.get("updated_at", ""))
    inv = f"{to}_{frm}"
    if inv in rates and float(rates[inv]["rate"]) != 0.0:
        rec = rates[inv]
        return 1.0 / float(rec["rate"]), str(rec.get("updated_at", ""))
    raise ValueError(f"Курс {frm}→{to} недоступен. Повторите попытку позже.")


# ---------- validators/format ----------
def _cur(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты должен быть непустой строкой")
    return code.strip().upper()


def _pos_amount(x) -> float:
    try:
        v = float(x)
    except Exception:
        raise ValueError("'amount' должен быть положительным числом")
    if v <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return v


def _fmt_amount(x: float) -> str:
    return f"{x:.4f}" if abs(x) < 1 else f"{x:.2f}"


def _currency_ok(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Неизвестная базовая валюта ''")
    return code.strip().upper()


# ============== PUBLIC USECASES ==============

@log_action("REGISTER")
def register(username: str, password: str) -> str:
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")
    username = username.strip()

    if _find_user_by_username(username):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = _next_user_id()
    salt = _generate_salt(username)
    hashed_password = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    users = _load_json(USERS_PATH, [])
    users.append({
        "user_id": user_id,
        "username": username,
        "hashed_password": hashed_password,
        "salt": salt,
        "registration_date": _utc_iso_now(),
    })
    _save_json(USERS_PATH, users)

    ports = _load_json(PORTFOLIOS_PATH, [])
    ports.append({"user_id": user_id, "wallets": {}})
    _save_json(PORTFOLIOS_PATH, ports)

    return f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"  # noqa: E501


@log_action("LOGIN")
def login(username: str, password: str) -> str:
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or not password:
        raise ValueError("Пароль не может быть пустым")
    username = username.strip()

    u = _find_user_by_username(username)
    if not u:
        raise ValueError(f"Пользователь '{username}' не найден")

    salt = u["salt"]
    hashed_try = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    if hashed_try != u["hashed_password"]:
        raise ValueError("Неверный пароль")

    _set_session(int(u["user_id"]), username)
    return f"Вы вошли как '{username}'"


def show_portfolio(base_currency: str = None) -> str:
    sess = _require_session()
    user_id = int(sess["user_id"])
    username = str(sess["username"])

    # если не передали --base, берём из Singleton-настроек
    base = _currency_ok(base_currency) if base_currency else _currency_ok(_DEFAULT_BASE)

    wallets = _load_user_portfolio(user_id)
    if not wallets:
        return "У вас пока нет кошельков. Добавьте валюту покупкой (команда buy)."

    # 3) базовая валюта
    base = _currency_ok(base_currency)

    # если все кошельки уже в базе — конвертация не нужна
    codes = [c.strip().upper() for c in wallets.keys()]
    if all(c == base for c in codes):
        lines = [f"Портфель пользователя '{username}' (база: {base}):"]
        total = 0.0
        for code in sorted(wallets.keys()):
            bal = float(wallets[code].get("balance", 0.0))
            lines.append(f"- {code}: {_fmt_amount(bal)}  → {bal:.2f} {base}")
            total += bal
        lines.append("---------------------------------")
        lines.append(f"ИТОГО: {total:,.2f} {base}")
        return "\n".join(lines)

    # 4) курсы и расчёт
    rates = _load_rates_map()
    if not _has_any_rate_for_base(base, rates):
        raise ValueError(f"Неизвестная базовая валюта '{base}'")

    lines = [f"Портфель пользователя '{username}' (база: {base}):"]
    total = 0.0
    for code in sorted(wallets.keys()):
        try:
            bal = float(wallets[code].get("balance", 0.0))
        except Exception:
            bal = 0.0
        code_up = code.strip().upper()
        rate = _get_rate(code_up, base, rates)
        value_in_base = bal * rate
        total += value_in_base
        bal_str = _fmt_amount(bal)
        lines.append(f"- {code_up}: {bal_str}  → {value_in_base:.2f} {base}")

    lines.append("---------------------------------")
    lines.append(f"ИТОГО: {total:,.2f} {base}")
    return "\n".join(lines)


@log_action("BUY", verbose=True)
def buy(currency: str, amount) -> str:
    sess = _require_session()
    user_id = int(sess["user_id"])

    # валидация кода валюты через реестр
    code = _cur(currency)  # проверка формата
    get_currency(code)  # бросит CurrencyNotFoundError при неизвестном коде

    # валидация amount
    amt = _pos_amount(amount)

    # портфель
    wallets = _load_user_portfolio(user_id)

    # текущие значения
    prev_code = float(wallets.get(code, {}).get("balance", 0.0))
    prev_usd = float(wallets.get("USD", {}).get("balance", 0.0))

    # курс currency->USD (для оценочной стоимости)
    try:
        rate, _ts = _get_rate_pair(code, "USD")
    except ValueError:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    cost_usd = amt * rate
    if prev_usd < cost_usd:
        # денег не хватает — по ТЗ бросаем InsufficientFundsError
        raise InsufficientFundsError(available=prev_usd, required=cost_usd, code="USD")

    # применяем через Wallet API
    w_code = Wallet(currency_code=code, balance=prev_code)
    w_usd = Wallet(currency_code="USD", balance=prev_usd)

    w_code.deposit(amt)
    # снимем нужные USD (мы уже проверили баланс выше)
    w_usd.withdraw(cost_usd)

    # сохраняем
    wallets[code] = {"balance": w_code.balance}
    wallets["USD"] = {"balance": w_usd.balance}
    _save_user_portfolio(user_id, wallets)

    return (
        f"Покупка выполнена: {amt:.4f} {code} по курсу {rate:.2f} USD/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {prev_code:.4f} → стало {w_code.balance:.4f}\n"
        f"- USD:  было {prev_usd:.2f} → стало {w_usd.balance:.2f}\n"
        f"Оценочная стоимость покупки: {cost_usd:.2f} USD"
    )


@log_action("SELL", verbose=True)
def sell(currency: str, amount) -> str:
    sess = _require_session()
    user_id = int(sess["user_id"])

    code = _cur(currency)
    if code == "USD":
        # по требованиям проекта мы не «продаём» USD
        raise ValueError("Продажа USD не поддерживается. Укажите другую валюту.")

    # проверка существования кода
    get_currency(code)  # может бросить CurrencyNotFoundError

    amt = _pos_amount(amount)
    wallets = _load_user_portfolio(user_id)

    prev_code = float(wallets.get(code, {}).get("balance", 0.0))
    prev_usd = float(wallets.get("USD", {}).get("balance", 0.0))

    if prev_code < amt:
        # по ТЗ — InsufficientFundsError
        raise InsufficientFundsError(available=prev_code, required=amt, code=code)

    try:
        rate, _ts = _get_rate_pair(code, "USD")
    except ValueError:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    revenue_usd = amt * rate

    w_code = Wallet(currency_code=code, balance=prev_code)
    w_usd = Wallet(currency_code="USD", balance=prev_usd)

    w_code.withdraw(amt)  # может бросить ValueError, но мы уже проверили баланс
    w_usd.deposit(revenue_usd)

    wallets[code] = {"balance": w_code.balance}
    wallets["USD"] = {"balance": w_usd.balance}
    _save_user_portfolio(user_id, wallets)

    return (
        f"Продажа выполнена: {amt:.4f} {code} по курсу {rate:.2f} USD/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {prev_code:.4f} → стало {w_code.balance:.4f}\n"
        f"- USD:  было {prev_usd:.2f} → стало {w_usd.balance:.2f}\n"
        f"Оценочная выручка: {revenue_usd:.2f} USD"
    )


def get_rate(frm: str, to: str) -> str:
    # TTL берём из SettingsLoader; делаем локальный импорт, чтобы исключить циклы
    try:
        from valutatrade_hub.infra.settings import SettingsLoader
        ttl = int(SettingsLoader().get("RATES_TTL_SECONDS", 300))
    except Exception:
        ttl = 300

    f = _cur(frm)
    t = _cur(to)

    # валидируем через реестр валют (может бросить CurrencyNotFoundError)
    get_currency(f)
    get_currency(t)

    # читаем снапшот и проверяем свежесть
    raw = _load_json(RATES_PATH, {})
    if not isinstance(raw, dict) or not raw or not _rates_are_fresh(raw, ttl):
        # формулировка под ТЗ/CLI
        raise ApiRequestError("данные курсов устарели")

    # получаем сам курс и метку времени пары
    rate, ts = _get_rate_pair(f, t)

    back_rate = 1.0 if rate == 0 else (1.0 / rate)
    ts_str = ts if ts else "неизвестно"
    return (
        f"Курс {f}→{t}: {rate:.8f} (обновлено: {ts_str})\n"
        f"Обратный курс {t}→{f}: {back_rate:.5f}"
    )


def _parse_iso(ts: str) -> float:
    """'2025-10-09T10:35:00' -> epoch seconds (0.0 если не парсится)."""
    try:
        # отбрасываем дробные секунды, если есть
        ts = ts.split(".")[0]
        tt = time.strptime(ts, "%Y-%m-%dT%H:%M:%S")
        return time.mktime(tt)
    except Exception:
        return 0.0


def _is_stale(ts: str, ttl: int) -> bool:
    if not ts:
        return True
    return (time.time() - _parse_iso(ts)) > ttl


def _maybe_refresh_rates() -> bool:
    """
    Заглушка «обновления» кеша курсов (Parser Service пока не подключён).
    Возвращаем False — чтобы сработал ApiRequestError при устаревшем кешe.
    """
    return False


def _get_rates_raw() -> dict:
    """Возвращает raw словарь из rates.json (со служебными полями)."""
    return _load_json(RATES_PATH, {})
