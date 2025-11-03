import shlex
from valutatrade_hub.core import usecases as uc

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
                frm = flags.get("from", "")
                to = flags.get("to", "")
                print(uc.get_rate(frm, to))
            else:
                print("Неизвестная команда. Введите 'help'.")
        except Exception as e:
            print(e)
