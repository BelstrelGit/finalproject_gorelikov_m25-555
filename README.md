# ValutaTrade Hub

Учебный проект: управление мультивалютным портфелем (Core Service) и сервис парсинга курсов (Parser Service).  
**Только стандартная библиотека Python**: HTTP — через `urllib`, JSON — `json`, парсинг CLI — `shlex`, время — `time`.

## Возможности

- Регистрация/вход.
- Портфель и кошельки (фиат/крипто), покупка/продажа с конвертацией через локальный кэш курсов.
- Реестр валют и пользовательские исключения.
- Логирование доменных операций через декоратор `@log_action` (ротация логов).
- Parser Service: сбор курсов из CoinGecko (крипто) и ExchangeRate-API (фиат), объединение и запись в `data/rates.json`.

## Установка

```bash
# 1) Установи зависимости (poetry)
poetry install

# если ругается на lock:
rm -f poetry.lock
poetry lock
poetry install
```

## Запуск

```bash

poetry run project```
CLI подскажет команды (help).

Конфигурация

TTL курсов (секунды) берётся из SettingsLoader (по умолчанию 300).

Можно создать config.json в корне (опционально):

{
  "RATES_TTL_SECONDS": 600
}

Ключ ExchangeRate-API для фиата: переменная окружения EXCHANGERATE_API_KEY.

export EXCHANGERATE_API_KEY="your_api_key_here"



Данные и кеш

data/users.json — пользователи ([] из коробки).

data/portfolios.json — портфели ([] из коробки).

data/rates.json — актуальные курсы (кеш; {} из коробки; заполняется update-rates).

data/exchange_rates.json — история снапшотов парсера ([] из коробки).

data/session.json — локальная сессия (не коммитим).

Логи

Пишутся в logs/actions.log (с ротацией). Папка logs/ не коммитится.



Основные команды
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



Примеры


> register --username alice --password 1234
> login --username alice --password 1234
> update-rates
> show-rates --top 2
> buy --currency BTC --amount 0.01
> sell --currency BTC --amount 0.005
> show-portfolio --base USD
> get-rate --from USD --to BTC


Архитектура

valutatrade_hub/
  core/
    currencies.py      # Currency/Fiat/Crypto + реестр
    exceptions.py      # кастомные исключения
    models.py          # User/Wallet/Portfolio
    usecases.py        # register/login/buy/sell/get-rate
    utils.py           # валидации/конвертации
  infra/
    settings.py        # Singleton SettingsLoader
    database.py        # (опц.) Singleton JSON I/O
  parser_service/
    config.py          # ParserConfig (dataclass)
    api_clients.py     # CoinGecko/ExchangeRate через urllib
    updater.py         # объединение источников + запись
    storage.py         # атомарная запись rates.json + история
  cli/
    interface.py       # единственная точка входа CLI
logging_config.py      # формат/ротация логов
decorators.py          # @log_action
data/
  users.json, portfolios.json, rates.json, exchange_rates.json


Разработка
# линт
poetry run ruff check .

# собрать пакет
poetry build


Примечания

Сеть для CoinGecko доступна без ключа. ExchangeRate-API требует ключ (EXCHANGERATE_API_KEY).

get-rate проверяет свежесть кеша (TTL) — при устаревших данных попросит обновить (update-rates).




Демонстрация работы базы данных (asciinema)

asciicast link


Установка и запуск (через Makefile)