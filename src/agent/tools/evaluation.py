import io
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

from agents import function_tool

from agent.tools.engine_file import get_engine_filepath


@function_tool
def test_correctness() -> str:
    """Run the public correctness evaluator for workspace/engine.py."""

    src_dir = "src"
    evaluator_dir = "src/evaluator"
    argv = [
        "test_correctness.py",
        "--engine",
        get_engine_filepath(),
        "--model-config",
        os.getenv("MODEL_CONFIG_FILEPATH", "/target/model_config.json"),
        "--weight-dir",
        os.getenv("WEIGHT_DIR", "target/weights"),
        "--device",
        os.getenv("EVALUATION_DEVICE", "auto"),
        "--atol",
        os.getenv("EVALUATION_ATOL", "1e-2"),
        "--rtol",
        os.getenv("EVALUATION_RTOL", "1e-2"),
    ]

    old_argv = sys.argv[:]
    inserted_paths: list[str] = []
    output = io.StringIO()

    try:
        for path in (src_dir, evaluator_dir):
            if path not in sys.path:
                sys.path.insert(0, path)
                inserted_paths.append(path)

        from evaluator.test_correctness import main

        sys.argv = argv
        with redirect_stdout(output), redirect_stderr(output):
            main()
    except Exception:
        return output.getvalue() + traceback.format_exc()
    finally:
        sys.argv = old_argv
        for path in inserted_paths:
            sys.path.remove(path)

    return output.getvalue()
