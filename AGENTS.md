# Agens Work Guide

## Agent Framework

When using the OpenAI Agents Python SDK, Read the [OpenAI Agents Python SDK documentation](https://openai.github.io/openai-agents-python/).

## Caution

1. If you update `.env` file, you need to update the `.env` section in the `README.MD` file as well.

## Code Style

1. You can not use Path(__file__).resolve().parents[2] to get the root directory of the project, you can just assume that the root directory is "mlsys_phase_3/".
