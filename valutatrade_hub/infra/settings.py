

import json
import time

class SettingsLoader:
    """
    Singleton для конфигурации проекта.
    Выбран способ через __new__ — самый простой и читаемый для учебного проекта:
      - один экземпляр на весь процесс,
      - не требует метаклассов,
      - корректно работает при множественных импортах.
    Источник: config.json в корне проекта (если нет — дефолты ниже).
    Примечание: в многопоточном окружении для идеальной строгости стоило бы добавить
    блокировку вокруг ветки if cls._instance is None, но для учебного проекта не требуется.
    """

    _instance = None
    _initialized = False

    # дефолтные значения — можно переопределить в config.json
    _DEFAULTS = {
        "DATA_DIR": "data",
        "USERS_PATH": "data/users.json",
        "PORTFOLIOS_PATH": "data/portfolios.json",
        "RATES_PATH": "data/rates.json",
        "SESSION_PATH": "data/session.json",
        "DEFAULT_BASE_CURRENCY": "USD",
        # Политика свежести курсов (секунды). Пока не используем в коде, но ключ есть.
        "RATES_TTL_SECONDS": 300,
        # Настройки логов (файл конфигурирования добавим в 3.4)
        "LOG_DIR": "logs",
        "LOG_FORMAT": "[%(asctime)s] %(levelname)s %(message)s",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config.json"):
        if not self.__class__._initialized:
            self._config_path = config_path
            self._cfg = dict(self._DEFAULTS)
            self._loaded_at = 0.0
            self._load()
            self.__class__._initialized = True

    # --------- внутреннее ---------
    def _load(self) -> None:
        """
        Грузим JSON-конфиг. Если файла нет/битый — остаёмся на дефолтах.
        """
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # поверх дефолтов накладываем пользовательские значения
                self._cfg.update(data)
        except FileNotFoundError:
            # ок — работаем на дефолтах
            pass
        except Exception:
            # битый конфиг — оставляем дефолты
            pass
        self._loaded_at = time.time()

    # --------- публичный интерфейс ---------
    def get(self, key, default=None):
        """
        Получить значение по ключу. Если ключа нет — вернуть default.
        """
        return self._cfg.get(key, default)

    def reload(self) -> None:
        """
        Явная перезагрузка конфигурации с диска.
        """
        # сброс и повторная загрузка
        self._cfg = dict(self._DEFAULTS)
        self._load()
