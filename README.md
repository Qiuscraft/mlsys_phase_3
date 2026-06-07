# Qiu Jun's Implementation for MLSYS Course Project Phase 3

## Technical Stack

- IDE: Visual Studio Code

## Installation

### Python Environment

```
pip install -r requirements.txt
```

### Model Weights Generation

If you are not in the submit environment, you must generate the model weights by yourself. You can run the following command in the root directory of the project:

```bash
mkdir /target
cp target/model_config.json /target/model_config.json
uv run scripts/generate_toy_weights.py \
  --config /target/model_config.json \
  --output /target/weights/model.pt
```

### .env File

```
OPENAI_API_KEY=sk-************************************************
# OPENAI_BASE_URL=https://******.****/v1/
OPENAI_DEFAULT_MODEL=gpt-5.5
# OPENAI_AGENTS_DISABLE_TRACING=true
ENGINE_FILEPATH=/workspace/engine.py
MODEL_CONFIG_FILEPATH=/target/model_config.json
WEIGHT_DIR=/target/weights
AGENT_MAX_TURNS=640
AGENT_EXIT_MAX_RUNTIME_SECONDS=1800
AGENT_EXIT_MAX_CHECKS=10
```

## Dev Environment

### Pre-Commit Hooks

This project uses pre-commit hooks to format and lint the code.

```bash
pre-commit install
```
