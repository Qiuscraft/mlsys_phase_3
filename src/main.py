import asyncio

from dotenv import load_dotenv
from loguru import logger

import agent.main as agent_main


def main():
    load_dotenv(override=True)

    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    asyncio.run(agent_main.main())


if __name__ == "__main__":
    main()
