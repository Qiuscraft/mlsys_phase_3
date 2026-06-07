import asyncio

from agents import Agent, Runner

from agent.hooks import ToolCallLogger
from agent.tools import engine_file
from util.file import read_file

agent = Agent(
    name="Agent",
    instructions=read_file("prompts/instructions.md"),
    tools=[
        engine_file.view_engine_file,
        engine_file.create_engine_file_from_template,
        engine_file.replace_in_engine_file,
        engine_file.delete_engine_file,
        engine_file.append_to_engine_file,
    ],
)


async def main():
    result = await Runner.run(
        agent,
        read_file("prompts/input.md"),
        hooks=ToolCallLogger(),
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
