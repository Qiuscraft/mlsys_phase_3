import asyncio
import json
import os
from loguru import logger

from agents import Agent, Runner

from agent.hooks import ToolCallLogger
from agent.run_state import (
    engine_validation_failures,
    reset_engine_validation_state,
)
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


def _exit_gate_failures() -> list[str]:
    failures = []
    exit_result = json.loads(exit_judge.judge_agent_exit())
    if not exit_result.get("can_exit", False):
        failures.append(
            "can_agent_exit returned false: "
            f"{exit_result.get('reason', 'unknown reason')} "
            f"(check_count={exit_result.get('check_count')}, "
            f"max_checks={exit_result.get('max_checks')}, "
            f"elapsed_seconds={exit_result.get('elapsed_seconds')}, "
            f"max_runtime_seconds={exit_result.get('max_runtime_seconds')})"
        )
    failures.extend(engine_validation_failures())
    return failures


def _gate_feedback(failures: list[str]) -> str:
    bullet_list = "\n".join(f"- {failure}" for failure in failures)
    return (
        "Your previous response attempted to exit, but the runner rejected it.\n\n"
        f"{bullet_list}\n\n"
        "Continue improving the engine. If you changed the engine, run "
        "test_correctness after the latest candidate edit, then run "
        "benchmark_throughput. Only benchmark_throughput can promote the "
        "candidate into the stable /workspace/engine.py file, and it will do so "
        "only when correctness has passed and performance improves. Only provide "
        "a final answer after can_agent_exit is true and the latest candidate "
        "revision has passed both checks."
    )


async def main():
    exit_judge.reset_agent_exit_judge()
    reset_engine_validation_state()

    hooks = ToolCallLogger()
    max_turns = int(os.getenv("AGENT_MAX_TURNS", 10))
    run_input = read_file("prompts/input.md")

    while True:
        result = await Runner.run(
            agent,
            run_input,
            hooks=hooks,
            max_turns=max_turns,
        )

        failures = _exit_gate_failures()
        if not failures:
            break

        logger.info(
            "final output rejected by runner gate:\n{}",
            "\n".join(f"- {failure}" for failure in failures),
        )

        run_input = result.to_input_list()
        run_input.append({"role": "user", "content": _gate_feedback(failures)})

    logger.info("final output: {}", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
