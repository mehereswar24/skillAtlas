"""LLM providers for the AI tutor.

One interface, two implementations: local Ollama when it is running, and a
deterministic retrieval-only responder when it is not. The tutor therefore
always answers — it just says plainly when it is answering without a model.
"""

from app.services.llm.base import ChatMessage, LLMProvider, LLMUnavailable
from app.services.llm.ollama import OllamaProvider
from app.services.llm.rules import RetrievalOnlyProvider

_provider: OllamaProvider | None = None


def get_provider() -> OllamaProvider:
    global _provider
    if _provider is None:
        _provider = OllamaProvider()
    return _provider


__all__ = [
    "ChatMessage",
    "LLMProvider",
    "LLMUnavailable",
    "OllamaProvider",
    "RetrievalOnlyProvider",
    "get_provider",
]
