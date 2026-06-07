import asyncio
import os
from loguru import logger

from agents import Agent, Runner

from agent.hooks import ToolCallLogger
from agent.tools import benchmark_analysis, engine_file, evaluation, exit_judge
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
        benchmark_analysis.analyze_benchmark_result,
        exit_judge.can_agent_exit,
    ],
)


async def main():
    exit_judge.reset_agent_exit_judge()
    result = await Runner.run(
        agent,
        read_file("prompts/input.md"),
        hooks=ToolCallLogger(),
        max_turns=int(os.getenv("AGENT_MAX_TURNS", 10)),
    )
    logger.info("final output: {}", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
