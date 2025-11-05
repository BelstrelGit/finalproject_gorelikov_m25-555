import shlex
from valutatrade_hub.core import usecases as uc
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,
)
from valutatrade_hub.core.currencies import list_supported_codes

HELP = """Команды:
  register        --username <str> --password <str>
  login           --username <str> --password <str>
  show-portfolio  [--base <str>]
  buy             --currency <str> --amount <float>
  sell            --currency <str> --amount <float>
  get-rate        --from <str> --to <str>
  help
  exit
"""

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
            else:
                print("Неизвестная команда. Введите 'help'.")
        except InsufficientFundsError as e:
            # Печатаем как есть (сообщение уже в нужном формате)
            print(e)
        except CurrencyNotFoundError as e:
            # Подсказка и список кодов
            print(e)
            codes = ", ".join(list_supported_codes())
            print(f"Поддерживаемые коды: {codes}")
            print("Подсказка: используйте 'get-rate --from USD --to <CODE>' для проверки курса.")
        except ApiRequestError as e:
            print(e)
            print("Попробуйте повторить позже или проверьте подключение к сети.")
        except Exception as e:
            # Остальные — как есть
            print(e)
