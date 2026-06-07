## Task

Generate an inference runtime for a small LLaMA-like decoder-only model.

## Introduction of the engine.py File

`workspace/engine.py` must define:

```python
def create_engine(model_config: dict, weight_dir: str, device: str = "cuda"):
    return Engine(...)
```

The returned object must support:

```python
class Engine:
    def prefill(self, request_ids, input_ids):
        ...

    def decode(self, request_ids, token_ids):
        ...

    def remove(self, request_ids):
        ...
```

### `prefill(request_ids, input_ids)`

Inputs:

- `request_ids`: a list of request IDs, such as `[0, 1, 2]`
- `input_ids`: a list of 1D `torch.Tensor` token sequences, one sequence per request

Output:

- a logits tensor with shape `[batch_size, vocab_size]`
- row `i` must contain the last-token logits for `request_ids[i]`

Calling `prefill(...)` for a request should create or replace that request's state. It should not clear the state of unrelated requests.

Implementation requirement:

- `prefill(...)` should do batched prefill work across the provided requests.
- During prefill, create real per-request, per-layer K/V cache state. The cache should contain K and V tensors for every transformer layer, not just token history.
- Keep hot request state on the target device. Avoid storing CPU token history if it forces later host/device copies.

### `decode(request_ids, token_ids)`

Inputs:

- `request_ids`: a list of existing request IDs
- `token_ids`: a 1D `torch.Tensor` with shape `[batch_size]`, one new token per request

Output:

- a logits tensor with shape `[batch_size, vocab_size]`
- row `i` must contain the last-token logits after appending `token_ids[i]` to `request_ids[i]`

Implementation requirement:

- `decode(...)` should do batched decode work across the provided requests.
- `decode(...)` should compute only the new token for each request. It should not rerun a full-sequence forward pass over stored token history.
- In decode, read the existing per-layer K/V cache, apply RoPE using the absolute position of the new token, write the new K/V into the cache, and attend the new query over cached K/V.
- Avoid `torch.cat` in the decode hot path when it rebuilds token history or K/V cache every step. Prefer preallocated or block-based cache tensors with sequence length/capacity metadata and indexed writes.
- Avoid rebuilding padded `[B, T, H, D]` K/V tensors for every decode token. If batching requests with different lengths requires padding, group similar lengths or otherwise minimize padding and copying.

### `remove(request_ids)`

Input:

- `request_ids`: a list of finished request IDs

This method does not need to return anything. It should release or delete the request state associated with those IDs.

## Performance Priorities

Optimize in this order:

1. Correctness and API semantics.
2. Real per-layer KV cache: prefill fills every layer's K/V, decode updates only the new cache position for every layer.
3. Batched prefill and batched decode across requests, with device-resident request state and efficient memory layout.
4. PyTorch primitives: use `torch.inference_mode`, tensor views/indexed writes, and `torch.nn.functional.scaled_dot_product_attention` where it is compatible with masks, causal behavior, RoPE, and grouped-query attention.
5. Better memory layout and request-state management: avoid CPU hot state, repeated `torch.cat`, per-token allocation churn, and padded KV rebuilds.
6. Triton kernels, C++/CUDA extensions, or custom kernels only after the PyTorch implementation is structurally correct. Good candidates are RMSNorm, RoPE, attention, MLP activation/projection glue, and cache update operations. Keep these changes small and benchmark-driven.

Do not replace a real KV-cache decode path with a faster-looking full-sequence recompute path. Throughput must improve without violating the cache and batching requirements.

## Workflow

init: Delete the old workspace/engine.py file, and create a workspace/engine.py file from the template.

edit: Edit the workspace/engine.py file to implement the required methods `prefill`, `decode`, and `remove`, you should consider the correctness of your implementation.

test: Use an external tool to test correctness of your implementation, if the test failed, back to step edit.

benchmark: Use an external tool to run the throughput benchmark.

performance test: Compare the current benchmark performance with the previous performance, if the current performance is not better, back to step edit.

check if exit now: Use the external tool to judge if you can exit. If you can exit and the latest engine edit has already passed correctness, go to step exit, else go to step edit.

improve: Use an external tool to analyse the output of step benchmark, recognize the bottleneck, and back to step edit to solve the bottleneck and improve the performance. Pass the raw JSON output from `benchmark_throughput` directly to `analyze_benchmark_result`; do not hand-write a shortened benchmark summary. If `analyze_benchmark_result` reports a parse or missing-field error, rerun it with the raw benchmark JSON before making more engine changes.

exit: Summarize the design and the performance of your implementation.

Do not exit after a code edit that has not been followed by `test_correctness`. If the final edit changes performance-sensitive code, also run `benchmark_throughput` before exit and report only benchmark numbers from the latest tested version.
