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


def _compact_source(source: str) -> str:
    return "".join(source.split())


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
    forward_source = _function_source(source, "_forward")
    forward_batch_source = _function_source(source, "_forward_batch")
    hot_decode_source = "\n".join(
        part for part in [decode_source, forward_source, forward_batch_source] if part
    )
    compact_hot_decode_source = _compact_source(hot_decode_source)
    source_lower = source.lower()
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

    if "torch.cat" in hot_decode_source and "torch.cat" not in decode_source:
        signals.append(
            {
                "name": "decode_hot_path_uses_torch_cat",
                "severity": "high",
                "evidence": "decode() reaches helper code that uses torch.cat, likely copying KV or token history during each generated token.",
            }
        )

    rebuilds_padded_kv_batch = (
        "old_kvs" in hot_decode_source
        and "torch.zeros" in hot_decode_source
        and (
            "maxlen=max" in compact_hot_decode_source
            or "max_len=max" in compact_hot_decode_source
        )
        and (
            "fullk" in hot_decode_source
            or "full_k" in hot_decode_source
            or "kv_cache" in hot_decode_source
        )
    )
    if rebuilds_padded_kv_batch:
        signals.append(
            {
                "name": "decode_rebuilds_padded_kv_batch",
                "severity": "high",
                "evidence": "decode hot path appears to rebuild padded batched K/V tensors from per-request caches.",
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

    has_named_cache = (
        "kv_cache" in source_lower
        or "k_cache" in source_lower
        or "v_cache" in source_lower
    )
    has_state_kv_cache = (
        ("'k':" in source or '"k":' in source or "['k']" in source or '["k"]' in source)
        and (
            "'v':" in source
            or '"v":' in source
            or "['v']" in source
            or '["v"]' in source
        )
        and ("self.states" in source or "self.state" in source)
    )
    has_cache_name = has_named_cache or has_state_kv_cache
    if not has_cache_name:
        signals.append(
            {
                "name": "no_obvious_kv_cache",
                "severity": "high",
                "evidence": "No obvious KV cache state was found in engine.py.",
            }
        )

    has_layered_cache_access = (
        "old_kvs" in hot_decode_source
        and ("[l]" in hot_decode_source or "[layer" in hot_decode_source)
    ) or (
        has_cache_name
        and ("num_layers" in source or "n_layers" in source)
        and (
            "append" in hot_decode_source
            or "copy_" in hot_decode_source
            or "][l]" in hot_decode_source
            or "][layer" in hot_decode_source
        )
    )
    if has_cache_name and not has_layered_cache_access:
        signals.append(
            {
                "name": "kv_cache_may_not_be_per_layer",
                "severity": "high",
                "evidence": "A KV cache name exists, but the decode hot path does not clearly index or update K/V cache per transformer layer.",
            }
        )

    if (
        not has_cache_name
        and "self.states" in source
        and ("tokens" in source_lower or "torch.cat" in decode_source)
    ):
        signals.append(
            {
                "name": "request_state_stores_token_history",
                "severity": "high",
                "evidence": "Request state appears to store token history instead of per-layer K/V tensors.",
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

    if "scaled_dot_product_attention" in source:
        signals.append(
            {
                "name": "uses_pytorch_sdpa",
                "severity": "info",
                "evidence": "The engine uses torch.nn.functional.scaled_dot_product_attention.",
            }
        )

    if "triton" not in source_lower:
        signals.append(
            {
                "name": "no_triton_kernels",
                "severity": "info",
                "evidence": "No Triton kernels were found in engine.py.",
            }
        )

    has_cuda_extension = (
        "cpp_extension" in source_lower
        or "load_inline" in source_lower
        or ".cu" in source_lower
        or "cudaextension" in source
    )
    if not has_cuda_extension:
        signals.append(
            {
                "name": "no_cpp_cuda_extensions",
                "severity": "info",
                "evidence": "No C++/CUDA extension or inline CUDA kernel was found in engine.py.",
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


def _optimization_ladder() -> list[dict[str, str]]:
    return [
        {
            "stage": "P0",
            "focus": "real per-layer KV cache",
            "notes": "prefill stores K/V tensors for every layer; decode projects only the new token and attends over cached K/V.",
        },
        {
            "stage": "P1",
            "focus": "batched prefill/decode and request-state layout",
            "notes": "batch work across requests while avoiding CPU token history, repeated torch.cat, padded KV rebuilds, and unnecessary host/device copies.",
        },
        {
            "stage": "P2",
            "focus": "PyTorch primitives",
            "notes": "use torch.inference_mode, torch.nn.functional.scaled_dot_product_attention, efficient tensor views, and in-place indexed cache writes where safe.",
        },
        {
            "stage": "P3",
            "focus": "Triton or C++/CUDA kernels",
            "notes": "after the PyTorch implementation is correct and structurally efficient, consider custom RMSNorm, RoPE, attention, MLP, and cache update kernels.",
        },
    ]


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

    if "decode_rebuilds_padded_kv_batch" in signal_names:
        primary_bottleneck = "decode_rebuilds_padded_kv_batch"
        _add_recommendation(
            recommendations,
            "P0",
            "Stop rebuilding padded KV batches in decode",
            "The decode hot path appears to copy per-request KV cache into newly allocated padded batch tensors each step.",
            "large",
            "Preallocate per-request K/V buffers with capacity, track each request's sequence length cursor, write the new K/V by slice assignment, and batch attention over active cache views without rebuilding padded [B, T, H, D] tensors each token.",
        )
    elif "kv_cache_may_not_be_per_layer" in signal_names:
        primary_bottleneck = "kv_cache_not_clearly_per_layer"
        _add_recommendation(
            recommendations,
            "P0",
            "Make the KV cache explicitly per-layer",
            "The engine has cache-like state, but it is not clearly storing and updating K/V tensors for each transformer layer.",
            "large",
            "Represent each request as K/V tensors indexed by layer, for example layer-major [num_layers, max_seq, num_kv_heads, head_dim] or a list with one K and V tensor per layer. prefill should fill every layer; decode should update only the new position for every layer.",
        )
    elif "decode_hot_path_uses_torch_cat" in signal_names:
        primary_bottleneck = "decode_copies_kv_cache_each_step"
        _add_recommendation(
            recommendations,
            "P0",
            "Avoid torch.cat in the decode hot path",
            "decode() reaches helper code that uses torch.cat, which usually reallocates and copies KV cache as generation grows.",
            "large",
            "Keep fixed-capacity or block-based K/V cache tensors and append new slots with indexed writes instead of concatenating old and new K/V tensors.",
        )
    elif (
        "decode_calls_full_forward" in signal_names
        or "no_obvious_kv_cache" in signal_names
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
    elif "request_state_stores_token_history" in signal_names:
        primary_bottleneck = "request_state_stores_token_history"
        _add_recommendation(
            recommendations,
            "P0",
            "Replace token-history state with KV cache state",
            "Keeping token history in request state usually forces decode to rerun full-sequence forward passes.",
            "large",
            "Keep active K/V cache tensors, current sequence length, and capacity per request. Do not use stored token history as the decode hot-path state after prefill.",
        )
    elif prefill_to_decode_ratio is not None and prefill_to_decode_ratio >= 8.0:
        primary_bottleneck = "decode_attention_or_cache_overhead"
        _add_recommendation(
            recommendations,
            "P1",
            "Profile decode cache and attention overhead",
            "Decode remains much slower than prefill even though a named KV cache is present.",
            "diagnostic",
            "Check whether decode still copies KV cache, pads requests to a large common length, materializes unnecessary score tensors, or launches many small kernels per token.",
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

    if (
        mixed_to_decode_ratio is not None
        and 0 < mixed_to_decode_ratio < 0.75
        and "decode_rebuilds_padded_kv_batch" not in signal_names
    ):
        if primary_bottleneck == "unknown":
            primary_bottleneck = "mixed_batching_padding_or_scheduling_overhead"
        _add_recommendation(
            recommendations,
            "P1",
            "Improve batch work across requests",
            "Mixed decode is much slower than uniform decode, which suggests padding, cache copying, or request scheduling overhead.",
            "medium_to_large",
            "Avoid rebuilding padded K/V tensors each decode step. Keep per-request KV buffers, write new slots in place, and group active requests by similar sequence length when batching attention.",
        )

    if (
        "request_state_stores_token_history" in signal_names
        and primary_bottleneck != "request_state_stores_token_history"
    ):
        _add_recommendation(
            recommendations,
            "P1",
            "Use KV-oriented request state",
            "Token-history request state is a poor memory layout for decode throughput.",
            "medium_to_large",
            "Store request state as device-resident cache tensors plus sequence length/capacity metadata. Keep token IDs only if they are needed outside the hot path.",
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
    elif "uses_pytorch_sdpa" in signal_names:
        evidence.append("engine uses PyTorch SDPA for at least one attention path.")

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

    if "no_triton_kernels" in signal_names:
        _add_recommendation(
            recommendations,
            "P3",
            "Consider Triton kernels after structural bottlenecks",
            "Once KV cache, batching, and PyTorch primitives are correct, Triton can fuse small decode-time kernels and reduce memory traffic.",
            "advanced",
            "Good candidates are RMSNorm, RoPE application, cache slot writes, fused QKV projection layouts, and decode attention. Only add Triton if correctness tests stay stable and benchmark results improve.",
        )

    if "no_cpp_cuda_extensions" in signal_names:
        _add_recommendation(
            recommendations,
            "P3",
            "Consider C++/CUDA extensions only for proven hot spots",
            "Custom compiled kernels can help but add build complexity and should follow profiler evidence.",
            "advanced",
            "Use torch.profiler first. If RMSNorm, RoPE, MLP activation, attention, or cache update kernels dominate runtime, consider a small C++/CUDA extension or inline CUDA kernel for that operation.",
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
        "optimization_ladder": _optimization_ladder(),
        "recommendations": recommendations,
        "next_actions": [
            "Apply the P0 recommendation first.",
            "Keep batched prefill and decode paths; do not optimize single-request code at the expense of batched request throughput.",
            "Run test_correctness after each engine change.",
            "Run benchmark_throughput again and pass the raw JSON output back into analyze_benchmark_result.",
        ],
    }
    return json.dumps(report, indent=2)
