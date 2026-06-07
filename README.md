# Qiu Jun's Implementation for MLSYS Course Project Phase 3

## Technical Stack

- IDE: Visual Studio Code
- Package Manager: uv

## Installation

### Python Environment

```bash
uv sync
```

### Pre-Commit Hooks

This project uses pre-commit hooks to format and lint the code.

```bash
pre-commit install
```

### Model Weights Generation

```bash
uv run scripts/generate_toy_weights.py \
  --config target/model_config.json \
  --output target/weights/model.pt
```

### .env File

```
OPENAI_API_KEY=sk-************************************************
# OPENAI_BASE_URL=https://******.****/v1/
OPENAI_DEFAULT_MODEL=gpt-5.5
# OPENAI_AGENTS_DISABLE_TRACING=true
ENGINE_FILEPATH=/workspace/engine.py
```
