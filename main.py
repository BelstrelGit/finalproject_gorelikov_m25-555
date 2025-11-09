from __future__ import annotations

import os
import threading

from valutatrade_hub.cli.interface import main as cli_main
from valutatrade_hub.parser_service.scheduler import run_scheduler


def _maybe_start_scheduler() -> None:
    """
    Фоновой планировщик курсов (опционально).
    Управление через переменные окружения:
      VTH_SCHEDULER_ENABLED=true|false (по умолчанию false)
      VTH_SCHEDULER_INTERVAL=300       (секунды)
      VTH_SCHEDULER_SOURCE=all|coingecko|exchangerate
    """
    enabled = os.getenv("VTH_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    interval = int(os.getenv("VTH_SCHEDULER_INTERVAL", "300"))
    source = os.getenv("VTH_SCHEDULER_SOURCE", "all").lower()

    t = threading.Thread(
        target=lambda: run_scheduler(interval=interval, source=source, iterations=None),
        name="vth-rates-scheduler",
        daemon=True,
    )
    t.start()


def main() -> None:
    _maybe_start_scheduler()
    cli_main()


if __name__ == '__main__':
    print("start valutatrade_hub")