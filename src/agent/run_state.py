import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class EngineValidationState:
    engine_revision: int = 0
    correctness_revision: int = -1
    benchmark_revision: int = -1
    committed_revision: int = -1
    best_score: float | None = None
    last_benchmark_score: float | None = None
    last_commit_message: str = "no candidate has been committed in this run"


@dataclass(frozen=True)
class CommitDecision:
    should_commit: bool
    reason: str


_lock = threading.Lock()
_state = EngineValidationState(best_score=None)


def _stable_engine_filepath() -> str:
    return os.path.abspath(
        os.path.expanduser(os.getenv("ENGINE_FILEPATH", "/workspace/engine.py"))
    )


def _best_metadata_filepath() -> str:
    stable_path = _stable_engine_filepath()
    default_path = os.path.join(os.path.dirname(stable_path), "engine_best.json")
    return os.path.abspath(
        os.path.expanduser(os.getenv("ENGINE_BEST_METADATA_FILEPATH", default_path))
    )


def _file_sha256(filepath: str) -> str | None:
    try:
        digest = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _load_initial_best_score() -> float | None:
    metadata_path = _best_metadata_filepath()
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    stable_hash = _file_sha256(_stable_engine_filepath())
    if stable_hash is None or payload.get("engine_sha256") != stable_hash:
        return None

    try:
        score = float(payload["best_score"])
    except (KeyError, TypeError, ValueError):
        return None
    if score <= 0:
        return None
    return score


def _write_best_metadata(
    *,
    score: float,
    benchmark_output: str,
    source: str,
    revision: int,
) -> None:
    metadata_path = _best_metadata_filepath()
    directory = os.path.dirname(metadata_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    payload = {
        "best_score": score,
        "engine_path": _stable_engine_filepath(),
        "engine_sha256": _file_sha256(_stable_engine_filepath()),
        "revision": revision,
        "source": source,
        "updated_at": time.time(),
        "benchmark": _parse_json_result(benchmark_output),
    }

    tmp_path = os.path.join(
        os.path.dirname(metadata_path),
        f".{os.path.basename(metadata_path)}.tmp",
    )
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, metadata_path)


def reset_engine_validation_state() -> None:
    global _state
    with _lock:
        _state = EngineValidationState(best_score=_load_initial_best_score())


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


def _normalize_benchmark_results(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            payload = payload["results"]
        elif isinstance(payload.get("benchmarks"), list):
            payload = payload["benchmarks"]
        else:
            return None

    if not isinstance(payload, list) or not payload:
        return None

    results = []
    required = {"elapsed_ms", "total_tokens"}
    for item in payload:
        if not isinstance(item, dict) or required.difference(item):
            return None
        results.append(item)
    return results


def calculate_benchmark_score(output: str) -> float | None:
    results = _normalize_benchmark_results(_parse_json_result(output))
    if not results:
        return None

    total_tokens = 0.0
    total_seconds = 0.0
    for item in results:
        try:
            total_tokens += float(item["total_tokens"])
            total_seconds += float(item["elapsed_ms"]) / 1000.0
        except (TypeError, ValueError):
            return None

    if total_tokens <= 0 or total_seconds <= 0:
        return None
    return total_tokens / total_seconds


def record_correctness_result(output: str) -> None:
    parsed = _parse_json_result(output)
    if isinstance(parsed, dict) and parsed.get("status") == "passed":
        with _lock:
            _state.correctness_revision = _state.engine_revision


def record_benchmark_result(output: str) -> float | None:
    score = calculate_benchmark_score(output)
    if score is not None:
        with _lock:
            _state.benchmark_revision = _state.engine_revision
            _state.last_benchmark_score = score
    return score


def record_committed_baseline_result(output: str) -> float | None:
    score = calculate_benchmark_score(output)
    if score is None:
        return None

    with _lock:
        if _state.best_score is None:
            _state.best_score = score
            _state.last_commit_message = (
                f"loaded existing stable engine baseline score {score:.3f}"
            )
            _write_best_metadata(
                score=score,
                benchmark_output=output,
                source="existing_stable_engine",
                revision=_state.committed_revision,
            )
    return score


def _min_improvement_ratio() -> float:
    raw_value = os.getenv("ENGINE_MIN_IMPROVEMENT_RATIO", "0")
    try:
        value = float(raw_value)
    except ValueError:
        return 0.0
    return max(value, 0.0)


def should_commit_candidate(candidate_score: float) -> CommitDecision:
    with _lock:
        revision = _state.engine_revision
        if _state.correctness_revision != revision:
            return CommitDecision(
                False,
                "candidate benchmark was recorded, but this revision has not passed "
                "correctness",
            )
        if _state.benchmark_revision != revision:
            return CommitDecision(
                False,
                "candidate benchmark has not been recorded for this revision",
            )

        if _state.best_score is None:
            return CommitDecision(True, "no stable benchmark baseline exists")

        threshold = _state.best_score * (1.0 + _min_improvement_ratio())
        if candidate_score > threshold:
            return CommitDecision(
                True,
                f"candidate score {candidate_score:.3f} is better than baseline "
                f"{threshold:.3f}",
            )

        return CommitDecision(
            False,
            f"candidate score {candidate_score:.3f} did not beat baseline {threshold:.3f}",
        )


def record_engine_committed(score: float, benchmark_output: str) -> None:
    with _lock:
        _state.committed_revision = _state.engine_revision
        _state.best_score = score
        _state.last_commit_message = (
            f"committed candidate revision {_state.engine_revision} with score "
            f"{score:.3f}"
        )
        _write_best_metadata(
            score=score,
            benchmark_output=benchmark_output,
            source="candidate_engine",
            revision=_state.engine_revision,
        )


def get_engine_validation_state() -> EngineValidationState:
    with _lock:
        return EngineValidationState(
            engine_revision=_state.engine_revision,
            correctness_revision=_state.correctness_revision,
            benchmark_revision=_state.benchmark_revision,
            committed_revision=_state.committed_revision,
            best_score=_state.best_score,
            last_benchmark_score=_state.last_benchmark_score,
            last_commit_message=_state.last_commit_message,
        )


def engine_validation_failures() -> list[str]:
    state = get_engine_validation_state()
    failures = []
    if state.correctness_revision != state.engine_revision:
        failures.append(
            "the latest candidate engine edit has not passed test_correctness"
        )
    if state.benchmark_revision != state.engine_revision:
        failures.append(
            "the latest candidate engine edit has not been measured by benchmark_throughput"
        )
    if state.best_score is None:
        failures.append(
            "no stable engine benchmark baseline is available; run benchmark_throughput"
        )
    return failures
