class Engine:
    def prefill(self, request_ids, input_ids): ...

    def decode(self, request_ids, token_ids): ...

    def remove(self, request_ids): ...


def create_engine(model_config: dict, weight_dir: str, device: str = "cuda"):
    return Engine(...)
