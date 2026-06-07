import os

from agents import function_tool

from agent.run_state import mark_engine_edited
from util.file import read_file


def get_engine_filepath() -> str:
    return os.path.expanduser(os.getenv("ENGINE_FILEPATH", "workspace/engine.py"))


@function_tool
def view_engine_file() -> str:
    """View the content of the workspace/engine.py file."""

    return read_file(get_engine_filepath())


@function_tool
def delete_old_and_create_engine_file_from_template():
    """Delete the old workspace/engine.py file and create a new one with the content from the template."""
    if os.path.exists(get_engine_filepath()):
        os.remove(get_engine_filepath())
    with open(get_engine_filepath(), "x", encoding="utf-8") as f:
        f.write(read_file("prompts/engine_template.py"))
    mark_engine_edited()


@function_tool
def replace_in_engine_file(old: str, new: str):
    """Replace text in the workspace/engine.py file."""
    with open(get_engine_filepath(), "r", encoding="utf-8") as f:
        text = f.read()
    if old not in text:
        raise ValueError(f"'{old}' not found in {get_engine_filepath()}")
    with open(get_engine_filepath(), "w", encoding="utf-8") as f:
        f.write(text.replace(old, new, 1))
    mark_engine_edited()


@function_tool
def append_to_engine_file(content: str):
    """Append content to the workspace/engine.py file."""
    with open(get_engine_filepath(), "a", encoding="utf-8") as f:
        f.write(content)
    mark_engine_edited()
