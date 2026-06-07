import asyncio
import os

from agents import Agent, Runner

from agent.hooks import ToolCallLogger
from agent.tools import engine_file, evaluation
from util.file import read_file

agent = Agent(
    name="Agent",
    instructions=read_file("prompts/instructions.md"),
    tools=[
        engine_file.view_engine_file,
        engine_file.delete_old_and_create_engine_file_from_template,
        engine_file.replace_in_engine_file,
        engine_file.append_to_engine_file,
        evaluation.test_correctness,
        evaluation.benchmark_throughput,
    ],
)


async def main():
    result = await Runner.run(
        agent,
        read_file("prompts/input.md"),
        hooks=ToolCallLogger(),
        max_turns=int(os.getenv("AGENT_MAX_TURNS", 10)),
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
