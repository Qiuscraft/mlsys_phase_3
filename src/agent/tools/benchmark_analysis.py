import json
import traceback
from typing import Any

from agents import function_tool

from agent.tools.engine_file import get_engine_filepath
from util.file import read_file


def _extract_json_payload(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ValueError("benchmark_output is empty")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        return payload

    raise ValueError("no JSON object or array found in benchmark_output")


def _normalize_benchmark_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            payload = payload["results"]
        elif isinstance(payload.get("benchmarks"), list):
            payload = payload["benchmarks"]
        else:
            raise ValueError("benchmark JSON object must contain a results list")

    if not isinstance(payload, list):
        raise ValueError("benchmark JSON payload must be a list")

    results = []
    required = {
        "case_name",
        "elapsed_ms",
        "prefill_tokens",
        "decode_tokens",
        "total_tokens",
        "tokens_per_second",
        "decode_tokens_per_second",
        "peak_memory_mb",
    }
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("benchmark result entries must be objects")
        missing = sorted(required.difference(item))
        if missing:
            raise ValueError(f"benchmark result missing fields: {missing}")
        results.append(item)

    return results


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _function_source(source: str, function_name: str) -> str:
    marker = f"    def {function_name}("
    start = source.find(marker)
    if start < 0:
        return ""

    next_start = source.find("\n    def ", start + len(marker))
    if next_start < 0:
        next_start = source.find("\n\ndef ", start + len(marker))
    if next_start < 0:
        return source[start:]
    return source[start:next_start]


def _engine_static_signals() -> dict[str, Any]:
    try:
        source = read_file(get_engine_filepath())
    except Exception as exc:
        return {
            "engine_read_error": str(exc),
            "signals": [],
        }

    prefill_source = _function_source(source, "prefill")
    decode_source = _function_source(source, "decode")
    signals = []

    if "_forward_batch" in decode_source:
        signals.append(
            {
                "name": "decode_calls_full_forward",
                "severity": "high",
                "evidence": "decode() calls _forward_batch(), which usually recomputes the whole sequence for every generated token.",
            }
        )

    if "torch.cat" in decode_source:
        signals.append(
            {
                "name": "decode_uses_torch_cat",
                "severity": "medium",
                "evidence": "decode() appends tokens with torch.cat(), reallocating sequence tensors over time.",
            }
        )

    if 'to("cpu"' in prefill_source or ".to('cpu'" in prefill_source:
        signals.append(
            {
                "name": "request_state_on_cpu",
                "severity": "medium",
                "evidence": "prefill() stores request token state on CPU, creating host/device copies in later forwards.",
            }
        )

    source_lower = source.lower()
    has_cache_name = (
        "kv_cache" in source_lower
        or "k_cache" in source_lower
        or "v_cache" in source_lower
    )
    if not has_cache_name:
        signals.append(
            {
                "name": "no_obvious_kv_cache",
                "severity": "high",
                "evidence": "No obvious KV cache state was found in engine.py.",
            }
        )

    if "scaled_dot_product_attention" not in source and "torch.softmax" in source:
        signals.append(
            {
                "name": "manual_attention_softmax",
                "severity": "medium",
                "evidence": "The engine appears to use explicit matmul + softmax attention instead of torch scaled_dot_product_attention or a fused kernel.",
            }
        )

    return {
        "engine_path": get_engine_filepath(),
        "signals": signals,
    }


def _add_recommendation(
    recommendations: list[dict[str, str]],
    priority: str,
    title: str,
    rationale: str,
    expected_impact: str,
    implementation_notes: str,
) -> None:
    recommendations.append(
        {
            "priority": priority,
            "title": title,
            "rationale": rationale,
            "expected_impact": expected_impact,
            "implementation_notes": implementation_notes,
        }
    )


@function_tool
def analyze_benchmark_result(benchmark_output: str) -> str:
    """Analyze benchmark_throughput JSON output and recommend the next engine optimization."""

    try:
        results = _normalize_benchmark_results(_extract_json_payload(benchmark_output))
    except Exception:
        return json.dumps(
            {
                "status": "error",
                "message": "Could not parse benchmark output.",
                "details": traceback.format_exc(),
                "expected_input": "Pass the raw JSON string returned by benchmark_throughput.",
            },
            indent=2,
        )

    by_case = {str(item["case_name"]): item for item in results}
    prefill = by_case.get("prefill", {})
    decode = by_case.get("decode", {})
    mixed = by_case.get("mixed", {})

    prefill_tps = _safe_float(prefill.get("tokens_per_second"))
    decode_tps = _safe_float(decode.get("decode_tokens_per_second"))
    mixed_decode_tps = _safe_float(mixed.get("decode_tokens_per_second"))
    decode_total_tps = _safe_float(decode.get("tokens_per_second"))
    peak_memory_values = [
        _safe_float(item.get("peak_memory_mb"))
        for item in results
        if _safe_float(item.get("peak_memory_mb")) > 0
    ]

    prefill_to_decode_ratio = _ratio(prefill_tps, decode_tps)
    mixed_to_decode_ratio = _ratio(mixed_decode_tps, decode_tps)
    decode_elapsed_ms = _safe_float(decode.get("elapsed_ms"))
    decode_tokens = _safe_float(decode.get("decode_tokens"))
    approx_decode_token_ms = _ratio(decode_elapsed_ms, decode_tokens)

    static = _engine_static_signals()
    signal_names = {
        signal["name"]
        for signal in static.get("signals", [])
        if isinstance(signal, dict) and "name" in signal
    }

    evidence = []
    recommendations: list[dict[str, str]] = []
    primary_bottleneck = "unknown"

    if prefill_to_decode_ratio is not None:
        evidence.append(
            f"prefill throughput is {prefill_to_decode_ratio:.1f}x decode-token throughput."
        )
    if approx_decode_token_ms is not None:
        evidence.append(
            f"decode case averages about {approx_decode_token_ms:.3f} ms per decoded token, including prefill overhead."
        )
    if mixed_to_decode_ratio is not None:
        evidence.append(
            f"mixed decode throughput is {mixed_to_decode_ratio:.2f}x the standalone decode case."
        )

    if (
        "decode_calls_full_forward" in signal_names
        or "no_obvious_kv_cache" in signal_names
        or (prefill_to_decode_ratio is not None and prefill_to_decode_ratio >= 8.0)
    ):
        primary_bottleneck = "decode_recomputes_full_sequence_without_kv_cache"
        _add_recommendation(
            recommendations,
            "P0",
            "Implement per-request KV cache",
            "Decode is much slower than prefill and the current engine appears to rerun full-sequence forward passes during decode.",
            "large",
            "Store K/V tensors for each layer during prefill. In decode, project only the new token, apply RoPE at the absolute position, append K/V to cache, and attend the new query over cached keys/values.",
        )

    if "decode_uses_torch_cat" in signal_names:
        _add_recommendation(
            recommendations,
            "P1",
            "Avoid torch.cat in the decode hot path",
            "Repeated torch.cat reallocates and copies request history as generation grows.",
            "medium",
            "Track sequence length separately and either preallocate token/KV buffers or append K/V cache blocks without rebuilding the full token tensor.",
        )

    if "request_state_on_cpu" in signal_names:
        _add_recommendation(
            recommendations,
            "P1",
            "Keep hot request state on the target device",
            "Moving token history from CPU to CUDA inside each forward adds avoidable transfer and synchronization cost.",
            "medium",
            "Store active request token state and KV cache tensors on the evaluation device. Only move data to CPU if remove() needs persistence, which it does not.",
        )

    if "manual_attention_softmax" in signal_names:
        _add_recommendation(
            recommendations,
            "P2",
            "Use fused attention where the tensor layout allows it",
            "Explicit score tensors and softmax add memory traffic and extra kernels, especially during prefill.",
            "medium",
            "After KV cache is correct, consider torch.nn.functional.scaled_dot_product_attention for prefill or decode attention if masks and GQA layout are compatible.",
        )

    if peak_memory_values:
        max_peak = max(peak_memory_values)
        min_peak = min(peak_memory_values)
        if min_peak > 0 and max_peak / min_peak >= 1.15:
            _add_recommendation(
                recommendations,
                "P2",
                "Reduce padding and temporary attention allocations",
                "Peak memory varies noticeably between benchmark cases, which often points to padded full-sequence attention tensors.",
                "small_to_medium",
                "Group active requests by similar sequence length where possible and avoid materializing full [B, H, T, T] score tensors in decode.",
            )

    if not recommendations:
        _add_recommendation(
            recommendations,
            "P1",
            "Run an operator-level profiler",
            "The benchmark ratios do not identify a clear structural bottleneck.",
            "diagnostic",
            "Use torch.profiler first to rank CUDA ops by self time, then use nsys/ncu only for the hottest kernels.",
        )

    summary = {
        "prefill_tokens_per_second": prefill_tps,
        "decode_tokens_per_second": decode_tps,
        "decode_total_tokens_per_second": decode_total_tps,
        "mixed_decode_tokens_per_second": mixed_decode_tps,
        "prefill_to_decode_tps_ratio": prefill_to_decode_ratio,
        "mixed_to_decode_tps_ratio": mixed_to_decode_ratio,
        "approx_decode_case_ms_per_decode_token": approx_decode_token_ms,
        "peak_memory_mb_by_case": {
            str(item["case_name"]): _safe_float(item.get("peak_memory_mb"))
            for item in results
        },
    }

    report = {
        "status": "ok",
        "primary_bottleneck": primary_bottleneck,
        "summary": summary,
        "evidence": evidence,
        "static_engine_analysis": static,
        "recommendations": recommendations,
        "next_actions": [
            "Apply the P0 recommendation first.",
            "Run test_correctness after each engine change.",
            "Run benchmark_throughput again and pass its output back into analyze_benchmark_result.",
        ],
    }
    return json.dumps(report, indent=2)
