
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from typing import Any, Dict, Iterable, List

__all__ = ["read_json", "write_json", "ensure_parent_dir"]


# ---------- Время/TTL ----------

def utc_iso_now() -> str:
    """Текущее UTC-время в ISO без миллисекунд: 'YYYY-MM-DDTHH:MM:SS'."""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def epoch_now() -> int:
    """Текущее время в секундах (Unix epoch)."""
    return int(time.time())


def _parse_iso_to_epoch(ts: str) -> int | None:
    """Попытка разобрать 'YYYY-MM-DDTHH:MM:SS' -> epoch секунд."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        tm = time.strptime(ts, "%Y-%m-%dT%H:%M:%S")
        return int(time.mktime(tm))
    except Exception:
        return None


def is_cache_fresh(last_refresh: Any, ttl_sec: int) -> bool:
    """
    Универсальная проверка «кэш свежий?»:
      - last_refresh может быть dict(snapshot), str(iso), int(epoch)
      - ttl_sec — допустимая «давность» в секундах
    """
    now = epoch_now()

    # 1) Снапшот целиком
    if isinstance(last_refresh, dict):
        snap = last_refresh
        # сначала пробуем явную epoch-метку
        lr_epoch = snap.get("last_refresh_epoch")
        if isinstance(lr_epoch, (int, float)):
            return now - int(lr_epoch) <= ttl_sec
        # затем ISO-метку
        lr_iso = snap.get("last_refresh")
        if isinstance(lr_iso, str):
            parsed = _parse_iso_to_epoch(lr_iso)
            return parsed is not None and (now - parsed <= ttl_sec)
        return False

    # 2) epoch
    if isinstance(last_refresh, (int, float)):
        return now - int(last_refresh) <= ttl_sec

    # 3) ISO-строка
    if isinstance(last_refresh, str):
        parsed = _parse_iso_to_epoch(last_refresh)
        return parsed is not None and (now - parsed <= ttl_sec)

    return False


# ---------- Валидации/нормализации ----------

def normalize_currency_code(code: str, *, min_len: int = 2, max_len: int = 5) -> str:
    """
    Приводит код к UPPER, проверяет, что это непустая строка заданной длины.
    Не проверяет «известность» кода — этим занимается реестр валют.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты должен быть непустой строкой")
    c = code.strip().upper()
    if not (min_len <= len(c) <= max_len):
        raise ValueError(f"Длина кода валюты должна быть {min_len}–{max_len} символов")
    if not re.fullmatch(r"[A-Z0-9]{%d,%d}" % (min_len, max_len), c):
        # Разрешим буквы/цифры — на случай тикеров типа "USDT".
        raise ValueError("Код валюты должен содержать только буквы/цифры латиницей")
    return c


def parse_positive_amount(x: Any) -> float:
    """Парсит сумму и гарантирует > 0. Сообщение — как в ТЗ."""
    try:
        v = float(x)
    except Exception:
        raise ValueError("'amount' должен быть положительным числом")
    if v <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return v


def fmt_amount(x: float) -> str:
    """Формат сумм: для |x|<1 — 4 знака, иначе 2."""
    return f"{x:.4f}" if abs(x) < 1 else f"{x:.2f}"


# ---------- Работа с кэшем курсов ----------

def flatten_rates_snapshot(snapshot: dict) -> Dict[str, float]:
    """
    Привести snapshot:
      {"BTC_USD": {"rate": 60000.0, "updated_at": "..."}, "source": "...", ...}
    к плоскому словарю: {"BTC_USD": 60000.0, ...}
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


def rate_from_flat(frm: str, to: str, flat: Dict[str, float]) -> float:
    """
    Находит курс frm→to в плоском словаре:
      - прямой ключ "FRM_TO"
      - иначе обратный "TO_FRM" (инверсия)
    """
    f = normalize_currency_code(frm)
    t = normalize_currency_code(to)
    if f == t:
        return 1.0
    k = f"{f}_{t}"
    if k in flat:
        return float(flat[k])
    inv = f"{t}_{f}"
    if inv in flat and float(flat[inv]) != 0.0:
        return 1.0 / float(flat[inv])
    raise ValueError(f"Нет курса для пары {f}→{t}")


# ---------- Парсинг CLI-флагов ----------

def parse_flags(tokens: Iterable[str]) -> Dict[str, Any]:
    """
    Превращает ['--a','1','--b'] -> {'a':'1','b':True}.
    Без зависимостей: работает поверх уже разбитых shlex'ом токенов.
    """
    flags: Dict[str, Any] = {}
    toks: List[str] = list(tokens)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("--"):
            key = t[2:]
            if i + 1 < len(toks) and not toks[i + 1].startswith("--"):
                flags[key] = toks[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            i += 1
    return flags


def ensure_parent_dir(path: str) -> None:
    """Создаёт родительскую директорию для файла, если её нет."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)


def read_json(path: str, default: Any = None) -> Any:
    """Безопасное чтение JSON. При отсутствии или битом файле вернёт default."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def write_json(path: str, data: Any, *, atomic: bool = True) -> None:
    """
    Запись JSON. По умолчанию — атомарно (tmp → rename) в той же директории.
    """
    ensure_parent_dir(path)
    if not atomic:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        return

    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=dir_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)  # атомарная подмена
    finally:
        # если os.replace не сработал — tmp уберётся здесь
        if os.path.exists(tmp) and os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
