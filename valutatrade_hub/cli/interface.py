from __future__ import annotations

import json
import shlex
from typing import Dict, List, Tuple

from valutatrade_hub.core import usecases as uc
from valutatrade_hub.core.currencies import list_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

HELP = """Команды:
  register        --username <str> --password <str>
  login           --username <str> --password <str>
  show-portfolio  [--base <str>]
  buy             --currency <str> --amount <float>
  sell            --currency <str> --amount <float>
  get-rate        --from <str> --to <str>

  update-rates    [--source coingecko|exchangerate]
  show-rates      [--currency <CODE>] [--top <N>] [--base <CODE>]

  help
  exit
"""



def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def _flat_from_snapshot(snapshot: dict) -> Dict[str, float]:
    """
    Привести snapshot вида:
      {"BTC_USD": {"rate": 60000.0, "updated_at": "..."}, "source": ..., ...}
    к плоскому виду: {"BTC_USD": 60000.0, ...}
    """
    out: Dict[str, float] = {}
    if not isinstance(snapshot, dict):
        return out
    for k, v in snapshot.items():
        if isinstance(v, dict) and "rate" in v:
            try:
                out[k] = float(v["rate"])
            except Exception:
                pass
    return out


def _get_rate_from_flat(frm: str, to: str, flat: Dict[str, float]) -> float:
    """
    Найти курс frm->to в плоском словаре (как в Core):
      - если есть прямой ключ "FRM_TO" — вернуть
      - иначе, если есть обратный "TO_FRM" — вернуть 1 / rate
      - иначе бросить ValueError
    """
    f = frm.strip().upper()
    t = to.strip().upper()
    if f == t:
        return 1.0
    k = f"{f}_{t}"
    if k in flat:
        return float(flat[k])
    inv = f"{t}_{f}"
    if inv in flat and float(flat[inv]) != 0.0:
        return 1.0 / float(flat[inv])
    raise ValueError(f"Нет курса для пары {f}→{t}")


def _parse_flags(tokens):
    flags = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--"):
            key = t[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[key] = tokens[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            i += 1
    return flags


# -------------------- update-rates --------------------

def update_rates(argline: str = "") -> None:
    """
    update-rates [--source coingecko|exchangerate]
      1) Инициализировать RatesUpdater (клиенты выбираются по флагу --source).
      2) Запустить run_update().
      3) Перехватить ApiRequestError и напечатать понятное сообщение.
      4) Сообщить об успехе и количестве обновлённых курсов.
    """
    # парсим аргументы как единую строку (чтобы вызывать из main через " ".join(rest))
    tokens = shlex.split(argline or "")
    source = None
    i = 0
    while i < len(tokens):
        if tokens[i] == "--source" and i + 1 < len(tokens):
            source = tokens[i + 1].strip().lower()
            i += 2
        else:
            i += 1

    # выбираем клиентов
    cfg = ParserConfig()
    clients = []
    if source in (None, "coingecko"):
        clients.append(CoinGeckoClient(cfg=cfg))
    if source in (None, "exchangerate"):
        clients.append(ExchangeRateApiClient(cfg=cfg))

    if not clients:
        print("ERROR: Укажите корректный источник: coingecko или exchangerate")
        return

    storage = RatesStorage(cfg=cfg)

    print("INFO: Starting rates update...")
    try:
        snapshot = RatesUpdater(clients, storage).run_update()
    except ApiRequestError as e:
        print(f"ERROR: Update failed. {e}")
        print("Please check logs for details.")
        return
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        print("Please check logs for details.")
        return

    # считаем количество пар
    count = sum(1 for v in snapshot.values() if isinstance(v, dict) and "rate" in v)
    last_refresh = snapshot.get("last_refresh", "unknown")
    print(f"Update successful. Total rates updated: {count}. Last refresh: {last_refresh}") # noqa: E501


# -------------------- show-rates --------------------

def cmd_show_rates(argline: str = "") -> None:
    """
    show-rates [--currency CODE] [--top N] [--base CODE]

    - Читает data/rates.json
    - Фильтрует (по валюте, top N по стоимости для крипто)
    - Опционально пересчитывает к другой базе (--base)
    - Печатает компактный список с last_refresh
    """
    # ВАЖНО: cfg нужен и для списка криптовалют (фильтр --top), и для путей
    cfg = ParserConfig()

    tokens = shlex.split(argline or "")
    want_currency = None  # пример: "BTC"
    want_top = None       # пример: 2
    want_base = None      # пример: "EUR"

    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--currency" and i + 1 < len(tokens):
            want_currency = tokens[i + 1].strip().upper()
            i += 2
        elif t == "--top" and i + 1 < len(tokens):
            try:
                want_top = int(tokens[i + 1])
            except Exception:
                want_top = None
            i += 2
        elif t == "--base" and i + 1 < len(tokens):
            want_base = tokens[i + 1].strip().upper()
            i += 2
        else:
            i += 1

    snapshot = _read_json(cfg.RATES_FILE_PATH, default={})
    if not isinstance(snapshot, dict) or not snapshot:
        print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.") # noqa: E501
        return

    last_refresh = snapshot.get("last_refresh", "unknown")
    flat = _flat_from_snapshot(snapshot)

    items: List[Tuple[str, float]] = []

    if want_base:
        # собираем все коды (левую часть KEY: CODE_BASE)
        codes = sorted({k.split("_")[0] for k in flat.keys() if "_" in k})
        if want_currency:
            codes = [c for c in codes if c == want_currency]

        for c in codes:
            try:
                r = _get_rate_from_flat(c, want_base, flat)
                items.append((f"{c}_{want_base}", float(r)))
            except Exception:
                pass

        if want_currency and not items:
            print(f"Курс для '{want_currency}' не найден в кеше.")
            return
    else:
        # без пересчёта базы — берём как есть
        for k, v in flat.items():
            frm = k.split("_", 1)[0] if "_" in k else k
            if want_currency and frm != want_currency:
                continue
            items.append((k, float(v)))

        if want_currency and not items:
            print(f"Курс для '{want_currency}' не найден в кеше.")
            return

    # --top: только криптовалюты, по убыванию курса
    if isinstance(want_top, int) and want_top > 0:
        crypto_set = set(cfg.CRYPTO_CURRENCIES)
        items = [t for t in items if t[0].split("_", 1)[0] in crypto_set]
        items.sort(key=lambda t: t[1], reverse=True)
        items = items[:want_top]
    else:
        items.sort(key=lambda t: t[0])

    if not items:
        print("Нет данных для отображения. Обновите кэш или настройте фильтры.")
        return

    print(f"Rates from cache (updated at {last_refresh}):")
    for k, v in items:
        s = f"{v:.6f}" if abs(v) < 1 else f"{v:.2f}"
        print(f"- {k}: {s}")



# -------------------- базовые команды Core --------------------

def main():
    print("ValutaTrade Hub CLI. Введите 'help' для справки.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nДо встречи!")
            break

        if not line.strip():
            continue
        if line.strip() == "help":
            print(HELP)
            continue
        if line.strip() == "exit":
            print("Пока!")
            break

        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Ошибка парсинга: {e}")
            continue

        cmd, *rest = parts
        flags = _parse_flags(rest)

        try:
            if cmd == "register":
                print(uc.register(flags.get("username", ""), flags.get("password", "")))
            elif cmd == "login":
                print(uc.login(flags.get("username", ""), flags.get("password", "")))
            elif cmd == "show-portfolio":
                print(uc.show_portfolio(flags.get("base", "USD")))
            elif cmd == "buy":
                print(uc.buy(flags.get("currency", ""), flags.get("amount", "")))
            elif cmd == "sell":
                print(uc.sell(flags.get("currency", ""), flags.get("amount", "")))
            elif cmd == "get-rate":
                print(uc.get_rate(flags.get("from", ""), flags.get("to", "")))
            elif cmd == "update-rates":
                # Передаём исходные аргументы как строку ("--source ...")
                update_rates(" ".join(rest))
            elif cmd == "show-rates":
                cmd_show_rates(" ".join(rest))
            else:
                print("Неизвестная команда. Введите 'help'.")
        except InsufficientFundsError as e:
            print(e)
        except CurrencyNotFoundError as e:
            print(e)
            codes = ", ".join(list_supported_codes())
            print(f"Поддерживаемые коды: {codes}")
            print("Подсказка: используйте 'get-rate --from USD --to <CODE>' для проверки курса.") # noqa: E501
        except ApiRequestError as e:
            print(e)
            print("Попробуйте повторить позже или проверьте подключение к сети.")
        except Exception as e:
            print(e)
