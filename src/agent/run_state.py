import json
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class EngineValidationState:
    engine_revision: int = 0
    correctness_revision: int = -1
    benchmark_revision: int = -1


_lock = threading.Lock()
_state = EngineValidationState()


def reset_engine_validation_state() -> None:
    global _state
    with _lock:
        _state = EngineValidationState()


def mark_engine_edited() -> None:
    with _lock:
        _state.engine_revision += 1


def _parse_json_result(output: str) -> Any:
    stripped = output.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def record_correctness_result(output: str) -> None:
    parsed = _parse_json_result(output)
    if isinstance(parsed, dict) and parsed.get("status") == "passed":
        with _lock:
            _state.correctness_revision = _state.engine_revision


def record_benchmark_result(output: str) -> None:
    parsed = _parse_json_result(output)
    if isinstance(parsed, list) and parsed:
        with _lock:
            _state.benchmark_revision = _state.engine_revision


def get_engine_validation_state() -> EngineValidationState:
    with _lock:
        return EngineValidationState(
            engine_revision=_state.engine_revision,
            correctness_revision=_state.correctness_revision,
            benchmark_revision=_state.benchmark_revision,
        )


def engine_validation_failures() -> list[str]:
    state = get_engine_validation_state()
    failures = []
    if state.correctness_revision != state.engine_revision:
        failures.append("the latest engine edit has not passed test_correctness")
    if state.benchmark_revision != state.engine_revision:
        failures.append(
            "the latest engine edit has not been measured by benchmark_throughput"
        )
    return failures
