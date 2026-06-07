# Agens Work Guide

## Package Manager

This project uses uv as the package manager.

You must replace all the commands by following rules:
- `python` -> `uv run`
- `pip install` -> `uv add`

## Agent Framework

When using the OpenAI Agents Python SDK, Read the [OpenAI Agents Python SDK documentation](https://openai.github.io/openai-agents-python/).

# Code Style

1. You can not use Path(__file__).resolve().parents[2] to get the root directory of the project, you can just consider the root directory is "mlsys_phase_3/".
