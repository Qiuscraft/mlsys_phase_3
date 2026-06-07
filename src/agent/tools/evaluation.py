import os

from agents import function_tool

from agent.run_state import (
    get_engine_validation_state,
    record_benchmark_result,
    record_committed_baseline_result,
    record_correctness_result,
    record_engine_committed,
    should_commit_candidate,
)
from agent.tools.engine_file import (
    commit_candidate_engine_file,
    ensure_candidate_engine_file,
    get_committed_engine_filepath,
    get_engine_filepath,
)
from util.module_runner import run_module_main


def _correctness_argv(engine_path: str) -> list[str]:
    return [
        "test_correctness.py",
        "--engine",
        engine_path,
        "--model-config",
        os.getenv("MODEL_CONFIG_FILEPATH", "/target/model_config.json"),
        "--weight-dir",
        os.getenv("WEIGHT_DIR", "/target/weights"),
        "--device",
        os.getenv("EVALUATION_DEVICE", "auto"),
        "--atol",
        os.getenv("EVALUATION_ATOL", "1e-2"),
        "--rtol",
        os.getenv("EVALUATION_RTOL", "1e-2"),
    ]


def _benchmark_argv(engine_path: str) -> list[str]:
    return [
        "benchmark_throughput.py",
        "--engine",
        engine_path,
        "--model-config",
        os.getenv("MODEL_CONFIG_FILEPATH", "target/model_config.json"),
        "--weight-dir",
        os.getenv("WEIGHT_DIR", "target/weights"),
        "--device",
        os.getenv("EVALUATION_DEVICE", "auto"),
        "--warmup",
        os.getenv("EVALUATION_WARMUP", "1"),
        "--repeat",
        os.getenv("EVALUATION_REPEAT", "3"),
    ]


def _run_correctness(engine_path: str) -> str:
    return run_module_main(
        "evaluator.test_correctness",
        _correctness_argv(engine_path),
        ["src", "src/evaluator"],
    )


def _run_benchmark(engine_path: str) -> str:
    return run_module_main(
        "evaluator.benchmark_throughput",
        _benchmark_argv(engine_path),
        ["src", "src/evaluator"],
    )


@function_tool
def test_correctness() -> str:
    """Run the public correctness evaluator for the candidate engine file."""

    ensure_candidate_engine_file()
    output = _run_correctness(get_engine_filepath())
    record_correctness_result(output)
    return output


@function_tool
def benchmark_throughput() -> str:
    """Run benchmark for the candidate engine and commit it only if it improves."""

    ensure_candidate_engine_file()
    output = _run_benchmark(get_engine_filepath())
    candidate_score = record_benchmark_result(output)
    if candidate_score is None:
        return output

    state = get_engine_validation_state()
    stable_path = get_committed_engine_filepath()
    if state.best_score is None and os.path.exists(stable_path):
        baseline_output = _run_benchmark(stable_path)
        record_committed_baseline_result(baseline_output)

    decision = should_commit_candidate(candidate_score)
    if decision.should_commit:
        commit_candidate_engine_file()
        record_engine_committed(candidate_score, output)
        return (
            output
            + "\n\n"
            + f"Candidate engine committed to {stable_path}: {decision.reason}."
        )

    return output + "\n\n" + f"Candidate engine was not committed: {decision.reason}."
