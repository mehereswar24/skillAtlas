"""Provider interface for chat and embeddings."""

from __future__ import annotations

from typing import AsyncIterator, Literal, Protocol, TypedDict


class ChatMessage(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[dict]
    # For role="tool"
    tool_call_id: str
    name: str


class LLMUnavailable(Exception):
    """The provider could not be reached or the model is not installed."""


class LLMProvider(Protocol):
    """Anything that can answer a chat and produce embeddings.

    Swapping in a hosted provider means implementing this and changing
    ``app.services.llm.get_provider`` — nothing in the routers has to change.
    """

    async def is_available(self) -> bool: ...

    async def stream_chat(
        self, messages: list[ChatMessage], options: dict | None = None
    ) -> AsyncIterator[str]:
        """Yield answer fragments as they are generated.

        ``options`` are provider sampling knobs set by this codebase — never by
        a request body. See ``OllamaProvider.stream_chat``.
        """
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input string."""
        ...
