import importlib
import io
import sys
import traceback
from collections.abc import Iterable
from contextlib import redirect_stderr, redirect_stdout


def run_module_main(
    module_name: str, argv: list[str], extra_sys_paths: Iterable[str]
) -> str:
    """Run a module's main() with temporary argv/sys.path and captured output."""

    old_argv = sys.argv[:]
    inserted_paths: list[str] = []
    output = io.StringIO()

    try:
        for path in extra_sys_paths:
            if path not in sys.path:
                sys.path.insert(0, path)
                inserted_paths.append(path)

        main = importlib.import_module(module_name).main
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
