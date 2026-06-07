import asyncio

from dotenv import load_dotenv

import agent.main as agent_main


def main():
    load_dotenv(override=True)

    asyncio.run(agent_main.main())


if __name__ == "__main__":
    main()
