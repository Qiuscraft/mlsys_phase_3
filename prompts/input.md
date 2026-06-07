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

### `decode(request_ids, token_ids)`

Inputs:

- `request_ids`: a list of existing request IDs
- `token_ids`: a 1D `torch.Tensor` with shape `[batch_size]`, one new token per request

Output:

- a logits tensor with shape `[batch_size, vocab_size]`
- row `i` must contain the last-token logits after appending `token_ids[i]` to `request_ids[i]`

### `remove(request_ids)`

Input:

- `request_ids`: a list of finished request IDs

This method does not need to return anything. It should release or delete the request state associated with those IDs.

## Workflow

init: Delete the old workspace/engine.py file, and create a workspace/engine.py file from the template.

edit: Edit the workspace/engine.py file to implement the required methods `prefill`, `decode`, and `remove`, you should consider the correctness of your implementation.

test: Use an external tool to test correctness of your implementation, if the test failed, back to step edit.

benchmark: Use an external tool to run the throughput benchmark.

performance test: Compare the current benchmark performance with the previous performance, if the current performance is not better, back to step edit.

check if exit now: Use the external tool to judge if you can exit. If you can exit, go to step exit, else go to step edit.

improve: Use an external tool to analyse the output of step benchmark, reconize the bottleneck, and back to step edit to solve the bottleneck and improve the performance.

exit: Summarize the design and the performance of your implementation.
