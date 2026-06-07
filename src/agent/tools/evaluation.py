import os

from agents import function_tool

from agent.run_state import record_benchmark_result, record_correctness_result
from agent.tools.engine_file import get_engine_filepath
from util.module_runner import run_module_main


@function_tool
def test_correctness() -> str:
    """Run the public correctness evaluator for workspace/engine.py."""

    argv = [
        "test_correctness.py",
        "--engine",
        get_engine_filepath(),
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

    output = run_module_main(
        "evaluator.test_correctness", argv, ["src", "src/evaluator"]
    )
    record_correctness_result(output)
    return output


@function_tool
def benchmark_throughput() -> str:
    """Run the public throughput benchmark for workspace/engine.py."""

    argv = [
        "benchmark_throughput.py",
        "--engine",
        get_engine_filepath(),
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

    output = run_module_main(
        "evaluator.benchmark_throughput", argv, ["src", "src/evaluator"]
    )
    record_benchmark_result(output)
    return output
