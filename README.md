# ValutaTrade Hub

Учебный проект: управление мультивалютным портфелем (**Core Service**) и сбор актуальных курсов (**Parser Service**).  

---

## Возможности

- Регистрация / вход.
- Портфель и кошельки (фиат/крипто), покупка/продажа с конвертацией по локальному кэшу.
- Иерархия валют (Fiat/Crypto) и пользовательские исключения.
- Логирование доменных операций через декоратор `@log_action` (ротация логов).
- Parser Service: сбор курсов из **CoinGecko** (крипто) и **ExchangeRate-API** (фиат), объединение и запись в `data/rates.json`.

---

## Требования

- Python 3.11+
- Poetry 1.7+ (рекомендуется)

---

## Установка и запуск

```bash

# Установка зависимостей (создаёт venv, ставит prod+dev пакеты, регистрирует скрипт `project`)
make install

# Сборка пакета (sdist + wheel появятся в dist/)
make build

# Публикация пакета (опционально; сработает, если настроен репозиторий/токены)
make publish

# Установка собранного wheel из dist/ в текущую среду — удобно для ручной проверки
make package-install

# Линтинг кода (ruff)
make lint

# Запуск CLI (эквивалент `poetry run project`)
make project

```




## Конфигурация

```Core (SettingsLoader)```

TTL кэша курсов (секунды) — RATES_TTL_SECONDS (по умолчанию 300).

Можно переопределить в `config.json` (в корне проекта):

TTL курсов (секунды) берётся из `SettingsLoader` (по умолчанию 300).

Можно создать `config.json` в корне (опционально):

`{
  "RATES_TTL_SECONDS": 600
}`

Ключ ExchangeRate-API для фиата: переменная окружения EXCHANGERATE_API_KEY.

`export EXCHANGERATE_API_KEY="your_api_key_here"`



# Данные и кеш

```
data/users.json — пользователи ([] из коробки).

data/portfolios.json — портфели ([] из коробки).

data/rates.json — актуальные курсы (кеш; {} из коробки; заполняется update-rates).

data/exchange_rates.json — история снапшотов парсера ([] из коробки).

data/session.json — локальная сессия (не коммитим).
```

## Логи

Пишутся в `logs/actions.log` (с ротацией). Папка logs/ не коммитится.

## Команды CLI
```
register        --username <str> --password <str>
login           --username <str> --password <str>
show-portfolio  [--base <str>]
buy             --currency <str> --amount <float>
sell            --currency <str> --amount <float>
get-rate        --from <str> --to <str>

update-rates    [--source coingecko|exchangerate]   # запустить парсер сейчас
show-rates      [--currency <CODE>] [--top <N>] [--base <CODE>]

help
exit
```



## Примеры

> register --username alice --password 1234
> login --username alice --password 1234
> update-rates
> show-rates --top 2
> buy --currency BTC --amount 0.01
> sell --currency BTC --amount 0.005
> show-portfolio --base USD
> get-rate --from USD --to BTC


## Автообновление курсов (планировщик, опционально)

Планировщик запускается автоматически вместе с CLI (в фоне). 
Управляется переменными окружения:
```
export VTH_SCHEDULER_ENABLED=true        # вкл/выкл
export VTH_SCHEDULER_INTERVAL=300        # интервал в секундах (реком. ≥ 300)
export VTH_SCHEDULER_SOURCE=all          # all|coingecko|exchangerate
```


## Архитектура
```
project-root/
├─ data/                               # Рабочие данные и кэши
│  ├─ users.json                       # пользователи (JSON-массив)
│  ├─ portfolios.json                  # портфели (JSON-массив)
│  ├─ rates.json                       # актуальные курсы для Core (кэш)
│  └─ exchange_rates.json              # история снапшотов Parser Service
│
├─ valutatrade_hub/
│  ├─ logging_config.py                # базовая настройка логов + ротация
│  ├─ decorators.py                    # @log_action для BUY/SELL/LOGIN/REGISTER
│  │
│  ├─ core/                            # Core Service: доменная логика
│  │  ├─ currencies.py                 # ABC Currency + FiatCurrency/CryptoCurrency + реестр
│  │  ├─ exceptions.py                 # InsufficientFundsError, CurrencyNotFoundError, ApiRequestError
│  │  ├─ models.py                     # User, Wallet, Portfolio
│  │  ├─ usecases.py                   # register/login/show-portfolio/buy/sell/get-rate (TTL, валидации)
│  │  └─ utils.py                      # общие валидации/конвертации/парсинг
│  │
│  ├─ infra/                           # инфраструктура/конфигурация
│  │  ├─ settings.py                   # Singleton SettingsLoader (TTL, пути, т.п.)
│  │
│  ├─ parser_service/                  # Parser Service: сбор и запись курсов
│  │  ├─ config.py                     # ParserConfig (dataclass): URL, ключи, списки валют, таймауты, пути
│  │  ├─ api_clients.py                # BaseApiClient + CoinGeckoClient/ExchangeRateApiClient (urllib)
│  │  ├─ storage.py                    # атомарная запись rates.json + ведение exchange_rates.json
│  │  ├─ updater.py                    # RatesUpdater: опрос источников, мердж, метаданные, логирование
│  │  └─ scheduler.py                  # run_scheduler(interval, source, iterations) — фоновые обновления
│  │
│  └─ cli/
│     └─ interface.py                  # единственная точка CLI: команды register/login/.../update-rates/show-rates
│
├─ main.py                             # вход: старт CLI + (опц.) фонового планировщика через env:
│                                      #   VTH_SCHEDULER_ENABLED=true|false
│                                      #   VTH_SCHEDULER_INTERVAL=300
│                                      #   VTH_SCHEDULER_SOURCE=all|coingecko|exchangerate
│
├─ Makefile                            # install/build/publish/package-install/lint/project
├─ pyproject.toml                      # метаданные пакета, зависимости, [tool.poetry.scripts].project="main:main"
├─ README.md                           # описание, команды, примеры, примечания
└─ .gitignore                          # .venv/, dist/, __pycache__/, .ruff_cache/, logs/, data/session.json и т.п.

```


# Примечания

Сеть для CoinGecko доступна без ключа. ExchangeRate-API требует ключ (EXCHANGERATE_API_KEY).

get-rate проверяет свежесть кеша (TTL) — при устаревших данных попросит обновить (update-rates).




## Демонстрация работы (asciinema)

[![asciicast](https://asciinema.org/a/TzTAwR46hA76l5fABvKVNRPUY)](https://asciinema.org/a/TzTAwR46hA76l5fABvKVNRPUY)





