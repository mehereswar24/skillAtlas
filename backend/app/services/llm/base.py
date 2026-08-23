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

    #: Which model answers, reported to clients through the tutor, interview
    #: and résumé status endpoints. Part of the interface rather than an
    #: implementation detail: those three routers read it off the provider, so
    #: a provider that spells it differently 500s every page that asks.
    chat_model: str

    async def is_available(self) -> bool:
        """Whether this provider can *generate*.

        False does not mean the feature is dead — callers fall back to
        deterministic retrieval — so a provider that cannot generate must
        answer False rather than True-because-it-can-respond. The status
        endpoints turn this straight into "generative" vs "retrieval-only".
        """
        ...

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
