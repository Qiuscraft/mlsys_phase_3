import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

import agent.main as agent_main


def backup_existing_log(log_path: Path) -> None:
    if not log_path.exists() or log_path.stat().st_size == 0:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = log_path.with_name(f"{log_path.stem}.{timestamp}{log_path.suffix}")
    suffix = 1
    while backup_path.exists():
        backup_path = log_path.with_name(
            f"{log_path.stem}.{timestamp}.{suffix}{log_path.suffix}"
        )
        suffix += 1

    log_path.rename(backup_path)


def main():
    load_dotenv(override=True)

    log_path = Path(os.getenv("LOG_FILEPATH") or "logs/app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing_log(log_path)

    logger.add(
        log_path,
        mode="w",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    asyncio.run(agent_main.main())


if __name__ == "__main__":
    main()
