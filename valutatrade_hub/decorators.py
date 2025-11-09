
import json
import re
from functools import wraps
from typing import Any, Callable, Tuple

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import get_logger

# --- helpers ---------------------------------------------------------

def _read_session() -> Tuple[str, int]:
    """Вернёт (username, user_id) из session.json или ('', 0)."""
    s = ("", 0)
    try:
        sess_path = SettingsLoader().session_path()
        with open(sess_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            username = str(data.get("username") or "")
            user_id = int(data.get("user_id") or 0)
            s = (username, user_id)
    except Exception:
        pass
    return s


def _extract_currency_amount(args, kwargs) -> Tuple[str, Any]:
    """
    Пытаемся взять currency и amount:
      - сперва kwargs['currency'/'amount'],
      - затем позиционно (buy/sell имеют сигнатуру (currency, amount)).
    """
    cur = kwargs.get("currency")
    amt = kwargs.get("amount")
    if cur is None and len(args) >= 1:
        cur = args[0]
    if amt is None and len(args) >= 2:
        amt = args[1]
    return (str(cur) if cur is not None else "-", amt if amt is not None else "-")


def _try_parse_rate_base_from_message(msg: str) -> Tuple[str, str]:
    """
    Ищем в тексте строку вида: 'по курсу 59300.00 USD/XXX'
    Возвращаем (rate_str, base). Если не нашли — ('n/a','USD').
    """
    if not isinstance(msg, str):
        return ("n/a", "USD")
    m = re.search(r"по\s+курсу\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Z]{3})/", msg)
    if m:
        rate, base = m.group(1), m.group(2)
        return (rate, base)
    return ("n/a", "USD")


def _try_extract_changes_verbose(msg: str) -> str:
    """
    Из ответа usecase собираем изменения вида:
      '- BTC: было 0.0000 → стало 0.0500'
      '- USD: было 3000.00 → стало  683.14'
    Возвращаем: 'BTC: 0.0000→0.0500; USD: 3000.00→683.14'
    """
    if not isinstance(msg, str):
        return ""
    pairs = []
    for line in msg.splitlines():
        m = re.search(
            r"^\s*-\s*([A-Z]{3,5}):\s*было\s*([0-9\.\,]+)\s*→\s*стало\s*([0-9\.\,]+)",
            line,
            re.IGNORECASE,
        )
        if m:
            code = m.group(1).upper()
            was = m.group(2).replace(",", "")
            now = m.group(3).replace(",", "")
            pairs.append(f"{code}: {was}→{now}")
    return "; ".join(pairs)


# --- decorator -------------------------------------------------------

def log_action(action: str, verbose: bool = False) -> Callable:
    """
    Декоратор логирования доменных операций.
    Поля лога:
      - action (BUY/SELL/REGISTER/LOGIN/...)
      - username / user_id
      - currency_code, amount
      - rate, base (если удаётся извлечь из ответа usecase)
      - result (OK/ERROR)
      - error_type / error_message (при исключении)
    Пример строки:
      INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC' amount=0.0500 rate=59300.00 base='USD' result=OK
    """  # noqa: E501
    logger = get_logger()

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            username, user_id = _read_session()
            currency, amount = _extract_currency_amount(args, kwargs)

            # нормализуем amount для печати
            try:
                amount_str = f"{float(amount):.4f}"
            except Exception:
                amount_str = str(amount)

            try:
                result = func(*args, *kwargs)
                rate_str, base = _try_parse_rate_base_from_message(result)
                msg = (
                    f"{action} user='{username or user_id}' "
                    f"currency='{currency}' amount={amount_str} "
                    f"rate={rate_str} base='{base}' result=OK"
                )
                if verbose:
                    changes = _try_extract_changes_verbose(result)
                    if changes:
                        msg += f" changes=\"{changes}\""
                logger.info(msg)
                return result
            except Exception as e:
                etype = e.__class__.__name__
                emsg = str(e)
                msg = (
                    f"{action} user='{username or user_id}' "
                    f"currency='{currency}' amount={amount_str} "
                    f"result=ERROR error_type={etype} error_message=\"{emsg}\""
                )
                logger.info(msg)
                raise

        return wrapper

    return decorator
