import json
import time

class SettingsLoader:
    """
    Singleton для конфигурации проекта.
    Реализация через __new__: один экземпляр на процесс,
    безопасно при множественных импортах.
    """

    _instance = None
    _initialized = False

    _DEFAULTS = {
        "DATA_DIR": "data",
        "USERS_PATH": "data/users.json",
        "PORTFOLIOS_PATH": "data/portfolios.json",
        "RATES_PATH": "data/rates.json",
        "SESSION_PATH": "data/session.json",
        "DEFAULT_BASE_CURRENCY": "USD",
        "RATES_TTL_SECONDS": 300,
        "LOG_DIR": "logs",
        "LOG_FILE": "actions.log",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "%(levelname)s %(asctime)s %(message)s",
        "LOG_DATEFMT": "%Y-%m-%dT%H:%M:%S",
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

    # --- internal ---
    def _load(self) -> None:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._cfg.update(data)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        self._loaded_at = time.time()

    # --- public API ---
    def get(self, key, default=None):
        return self._cfg.get(key, default)

    def reload(self) -> None:
        self._cfg = dict(self._DEFAULTS)
        self._load()

    # удобные геттеры путей/ключей
    def users_path(self) -> str:
        return self.get("USERS_PATH", "data/users.json")

    def portfolios_path(self) -> str:
        return self.get("PORTFOLIOS_PATH", "data/portfolios.json")

    def rates_path(self) -> str:
        return self.get("RATES_PATH", "data/rates.json")

    def session_path(self) -> str:
        return self.get("SESSION_PATH", "data/session.json")

    def default_base_currency(self) -> str:
        return self.get("DEFAULT_BASE_CURRENCY", "USD")

    def rates_ttl_seconds(self) -> int:
        try:
            return int(self.get("RATES_TTL_SECONDS", 300))
        except Exception:
            return 300
