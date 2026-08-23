"""LLM providers for the AI tutor.

One interface, three implementations: hosted OpenRouter, local Ollama, and a
deterministic retrieval-only responder for when neither is reachable. The tutor
therefore always answers — it just says plainly when it is answering without a
model.

Which one runs is decided by `settings.llm_provider`. The default, `"auto"`,
resolves on the presence of an OpenRouter key rather than on the environment
name, because that is the fact that actually determines what will work: a
serverless function has no Ollama to reach, and a laptop with Ollama running
and no key must not start dialling a hosted API.
"""

from app.config import settings
from app.services.llm.base import ChatMessage, LLMProvider, LLMUnavailable
from app.services.llm.ollama import OllamaProvider
from app.services.llm.openrouter import OpenRouterProvider
from app.services.llm.rules import RetrievalOnlyProvider

_provider: LLMProvider | None = None


def _build() -> LLMProvider:
    choice = settings.llm_provider
    if choice == "auto":
        choice = "openrouter" if settings.openrouter_api_key else "ollama"

    if choice == "openrouter":
        return OpenRouterProvider()
    if choice == "retrieval":
        return RetrievalOnlyProvider()
    return OllamaProvider()


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = _build()
    return _provider


def reset_provider() -> None:
    """Drop the cached provider so the next call re-reads settings.

    Only for tests, which change `llm_provider` between cases; the process
    otherwise keeps one provider for its lifetime.
    """
    global _provider
    _provider = None


__all__ = [
    "ChatMessage",
    "LLMProvider",
    "LLMUnavailable",
    "OllamaProvider",
    "OpenRouterProvider",
    "RetrievalOnlyProvider",
    "get_provider",
    "reset_provider",
]
