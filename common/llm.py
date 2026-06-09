"""Shared LLM factory for all agents.

Alibaba Cloud Model Studio exposes Qwen through an OpenAI-compatible API,
so LangChain's ChatOpenAI client can talk to it by changing the base URL.
"""

import os

from langchain_openai import ChatOpenAI

DEFAULT_DASHSCOPE_MODEL = "qwen3-vl-plus-2025-09-23"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at Alibaba DashScope by default."""
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("DASHSCOPE_MODEL") or os.getenv("OPENROUTER_MODEL") or DEFAULT_DASHSCOPE_MODEL
    base_url = os.getenv("DASHSCOPE_BASE_URL") or os.getenv(
        "OPENROUTER_BASE_URL",
        DEFAULT_DASHSCOPE_BASE_URL,
    )

    if not api_key or api_key == "your_alibaba_cloud_model_studio_key_here":
        raise ValueError(
            "Missing DASHSCOPE_API_KEY. Put your Alibaba Cloud Model Studio API key in .env."
        )

    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base=base_url,
    )
