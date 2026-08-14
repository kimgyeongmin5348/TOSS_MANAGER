"""Provider-neutral inputs for a future Porto Manager LLM connection."""

from .context import (
    build_llm_messages,
    build_portfolio_manager_context,
    build_symbol_manager_context,
)
from .nvidia import NvidiaLLMClient, NvidiaLLMError

__all__ = [
    "build_llm_messages",
    "build_portfolio_manager_context",
    "build_symbol_manager_context",
    "NvidiaLLMError",
    "NvidiaLLMClient",
]
