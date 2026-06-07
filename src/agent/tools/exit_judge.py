import json
import os
import threading
import time

from agents import function_tool


DEFAULT_MAX_RUNTIME_SECONDS = 1800.0
DEFAULT_MAX_CHECKS = 3
MAX_RUNTIME_ENV = "AGENT_EXIT_MAX_RUNTIME_SECONDS"
MAX_CHECKS_ENV = "AGENT_EXIT_MAX_CHECKS"

_lock = threading.Lock()
_started_at = time.monotonic()
_check_count = 0


def _env_float(name: str, default: float) -> tuple[float, str | None]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default, None

    try:
        value = float(raw_value)
    except ValueError:
        return default, f"{name} must be a number, got {raw_value!r}; using {default}."

    if value <= 0:
        return (
            default,
            f"{name} must be greater than 0, got {raw_value!r}; using {default}.",
        )

    return value, None


def _env_int(name: str, default: int) -> tuple[int, str | None]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except ValueError:
        return (
            default,
            f"{name} must be an integer, got {raw_value!r}; using {default}.",
        )

    if value <= 0:
        return (
            default,
            f"{name} must be greater than 0, got {raw_value!r}; using {default}.",
        )

    return value, None


def reset_agent_exit_judge() -> None:
    """Reset run-local exit judge state before starting an agent run."""

    global _check_count, _started_at
    with _lock:
        _started_at = time.monotonic()
        _check_count = 0


@function_tool
def can_agent_exit() -> str:
    """Judge whether the agent can exit based on run time or how many times this tool has been called."""

    return judge_agent_exit()


def judge_agent_exit() -> str:
    """Return the exit judgment JSON without SDK tool wrapping."""

    max_runtime_seconds, runtime_error = _env_float(
        MAX_RUNTIME_ENV,
        DEFAULT_MAX_RUNTIME_SECONDS,
    )
    max_checks, checks_error = _env_int(MAX_CHECKS_ENV, DEFAULT_MAX_CHECKS)

    global _check_count
    with _lock:
        _check_count += 1
        check_count = _check_count
        elapsed_seconds = time.monotonic() - _started_at

    runtime_exceeded = elapsed_seconds > max_runtime_seconds
    checks_exceeded = check_count > max_checks
    can_exit = runtime_exceeded or checks_exceeded

    reasons = []
    if runtime_exceeded:
        reasons.append(
            f"elapsed_seconds {elapsed_seconds:.3f} exceeded max_runtime_seconds {max_runtime_seconds:.3f}"
        )
    if checks_exceeded:
        reasons.append(f"check_count {check_count} exceeded max_checks {max_checks}")

    result = {
        "can_exit": can_exit,
        "reason": "; ".join(reasons)
        if reasons
        else "exit limits have not been reached",
        "elapsed_seconds": round(elapsed_seconds, 3),
        "max_runtime_seconds": max_runtime_seconds,
        "check_count": check_count,
        "max_checks": max_checks,
        "env": {
            "max_runtime_seconds": MAX_RUNTIME_ENV,
            "max_checks": MAX_CHECKS_ENV,
        },
    }

    config_errors = [error for error in (runtime_error, checks_error) if error]
    if config_errors:
        result["config_errors"] = config_errors

    return json.dumps(result, indent=2)
