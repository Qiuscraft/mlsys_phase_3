import os
import shutil

from agents import function_tool

from agent.run_state import mark_engine_edited
from util.file import read_file


def _expand_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _candidate_path_for(committed_path: str) -> str:
    directory = os.path.dirname(committed_path)
    filename = os.path.basename(committed_path)
    stem, suffix = os.path.splitext(filename)
    return os.path.join(directory, f"{stem}_candidate{suffix or '.py'}")


def _ensure_parent_directory(filepath: str) -> None:
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)


def get_committed_engine_filepath() -> str:
    return _expand_path(os.getenv("ENGINE_FILEPATH", "/workspace/engine.py"))


def get_candidate_engine_filepath() -> str:
    committed_path = get_committed_engine_filepath()
    candidate_path = _expand_path(
        os.getenv("ENGINE_CANDIDATE_FILEPATH", _candidate_path_for(committed_path))
    )
    if candidate_path == committed_path:
        candidate_path = _candidate_path_for(committed_path)
    return candidate_path


def get_engine_filepath() -> str:
    """Return the candidate engine path used for agent edits and evaluation."""

    return get_candidate_engine_filepath()


def ensure_candidate_engine_file() -> None:
    """Create the candidate engine from the stable engine or template if needed."""

    candidate_path = get_candidate_engine_filepath()
    if os.path.exists(candidate_path):
        return

    committed_path = get_committed_engine_filepath()
    _ensure_parent_directory(candidate_path)
    if os.path.exists(committed_path):
        shutil.copyfile(committed_path, candidate_path)
        return

    with open(candidate_path, "x", encoding="utf-8") as f:
        f.write(read_file("prompts/engine_template.py"))


def commit_candidate_engine_file() -> None:
    """Atomically replace the stable engine with the candidate engine."""

    candidate_path = get_candidate_engine_filepath()
    committed_path = get_committed_engine_filepath()
    ensure_candidate_engine_file()
    _ensure_parent_directory(committed_path)

    tmp_path = os.path.join(
        os.path.dirname(committed_path),
        f".{os.path.basename(committed_path)}.tmp",
    )

    with open(candidate_path, "r", encoding="utf-8") as src:
        content = src.read()
    with open(tmp_path, "w", encoding="utf-8") as dst:
        dst.write(content)
        dst.flush()
        os.fsync(dst.fileno())

    os.replace(tmp_path, committed_path)


@function_tool
def view_engine_file() -> str:
    """View the content of the candidate engine file."""

    ensure_candidate_engine_file()
    return read_file(get_candidate_engine_filepath())


@function_tool
def delete_old_and_create_engine_file_from_template():
    """Delete the old candidate engine file and create a new one from the template."""

    candidate_path = get_candidate_engine_filepath()
    if os.path.exists(candidate_path):
        os.remove(candidate_path)
    _ensure_parent_directory(candidate_path)
    with open(candidate_path, "x", encoding="utf-8") as f:
        f.write(read_file("prompts/engine_template.py"))
    mark_engine_edited()


@function_tool
def replace_in_engine_file(old: str, new: str):
    """Replace text in the candidate engine file."""

    ensure_candidate_engine_file()
    candidate_path = get_candidate_engine_filepath()
    with open(candidate_path, "r", encoding="utf-8") as f:
        text = f.read()
    if old not in text:
        raise ValueError(f"'{old}' not found in {candidate_path}")
    with open(candidate_path, "w", encoding="utf-8") as f:
        f.write(text.replace(old, new, 1))
    mark_engine_edited()


@function_tool
def append_to_engine_file(content: str):
    """Append content to the candidate engine file."""

    ensure_candidate_engine_file()
    with open(get_candidate_engine_filepath(), "a", encoding="utf-8") as f:
        f.write(content)
    mark_engine_edited()
