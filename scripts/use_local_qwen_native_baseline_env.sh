#!/usr/bin/env bash

export DASHAGENT_LLM_PROVIDER=openai
export OPENAI_BASE_URL="${LOCAL_QWEN_NATIVE_BASE_URL:-http://127.0.0.1:8000/v1}"
export OPENAI_MODEL="${LOCAL_QWEN_NATIVE_SERVED_MODEL:-local-qwen-native-baseline}"
export OPENAI_API_KEY="${LOCAL_QWEN_NATIVE_API_KEY:-local-qwen-native-token}"
export LLM_ENDPOINT_LABEL=local_qwen_native_baseline
export V2_ENABLE_SCHEMA_BINDING="${V2_ENABLE_SCHEMA_BINDING:-0}"
