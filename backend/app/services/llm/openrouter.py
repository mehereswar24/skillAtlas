"""OpenRouter provider.

A hosted stand-in for Ollama, which is what production needs: there is no GPU
behind a serverless function, so the local provider has nothing to talk to.
The wire format is OpenAI's chat-completions API, which OpenRouter fronts for
every model it brokers, so the model is a configuration value rather than a
code change.

One capability is genuinely missing rather than unimplemented: **OpenRouter
brokers chat completions, not embeddings.** ``embed`` therefore raises
``NotImplementedError``, which is not a stub — ``rag.retrieve`` already catches
it and falls back to BM25 keyword search. The consequence is worth stating
plainly: with this provider selected, the 7,427 stored concept vectors go
unused and retrieval is lexical. Vector search returns the moment a provider
that can embed is configured, because the vectors are still in the database.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.config import settings
from app.services.llm.base import ChatMessage, LLMUnavailable


class OpenRouterProvider:
    def __init__(
        self,
        api_key: str | None = None,
        chat_model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        fallback_models: list[str] | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.chat_model = chat_model or settings.openrouter_model
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.timeout = timeout or settings.openrouter_timeout_sec
        self.fallback_models = (
            fallback_models
            if fallback_models is not None
            else [m for m in settings.openrouter_fallback_models if m != self.chat_model]
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter attributes traffic with these and shows the app on its
        # leaderboards. Both are optional and neither carries user data.
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_app_name:
            headers["X-Title"] = settings.openrouter_app_name
        return headers

    async def is_available(self) -> bool:
        """True when a key is configured and OpenRouter accepts it.

        Deliberately hits `/key` rather than sending a completion: the free
        tier allows only a handful of requests a day, and spending one of them
        on a health check would be self-defeating. `/key` is not billed and is
        not counted against the model rate limit.
        """
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/key", headers=self._headers()
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _payload(self, messages: list[ChatMessage], options: dict | None) -> dict:
        opts = dict(options or {})
        # Translate the two Ollama knobs this codebase actually sets. `num_ctx`
        # has no OpenAI equivalent — context length is a property of the model
        # on a hosted provider — so it is dropped rather than passed through as
        # a parameter the API would reject.
        max_tokens = opts.pop("num_predict", None)
        temperature = opts.pop("temperature", 0.3)
        opts.pop("num_ctx", None)

        payload: dict = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            **opts,
        }
        # OpenRouter's model routing: if the first entry is rate-limited or
        # down it tries the next, server-side, within the same request. Free
        # model pools are shared between everyone and return upstream 429s
        # unpredictably, so this is what keeps the tutor answering.
        if self.fallback_models:
            payload["models"] = [self.chat_model, *self.fallback_models]
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    @staticmethod
    def _fail(response: httpx.Response) -> LLMUnavailable:
        """Turn an HTTP error into something a maintainer can act on."""
        detail = ""
        try:
            detail = str(response.json().get("error", {}).get("message", ""))
        except (ValueError, AttributeError):
            detail = response.text[:200]
        if response.status_code == 429:
            return LLMUnavailable(
                "OpenRouter rate limit reached. Free models allow 20 requests a "
                "minute and 50 a day on an account with no credits; buying "
                "credits raises the daily cap. " + detail
            )
        if response.status_code in (401, 403):
            return LLMUnavailable(
                f"OpenRouter rejected the API key ({response.status_code}). {detail}"
            )
        return LLMUnavailable(
            f"OpenRouter returned {response.status_code}. {detail}"
        )

    async def stream_chat(
        self, messages: list[ChatMessage], options: dict | None = None
    ) -> AsyncIterator[str]:
        """Stream an answer as server-sent events.

        `options` is for callers *inside* this codebase — the anonymous helper
        caps the reply length with it. It is never populated from a request
        body; an unauthenticated caller must not choose the model or its
        sampling parameters.
        """
        payload = {**self._payload(messages, options), "stream": True}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise self._fail(response)
                    async for line in response.aiter_lines():
                        line = line.strip()
                        # OpenRouter sends `: OPENROUTER PROCESSING` keep-alive
                        # comments while a cold model loads. They are valid SSE
                        # and must not be parsed as JSON.
                        if not line or line.startswith(":"):
                            continue
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("error"):
                            raise LLMUnavailable(str(chunk["error"]))
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        # Reasoning models stream their scratchpad in
                        # `reasoning`. That is not an answer and must not reach
                        # the learner, so only `content` is forwarded.
                        fragment = delta.get("content")
                        if fragment:
                            yield fragment
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"OpenRouter request failed: {exc}") from exc

    async def chat_with_tools(
        self, messages: list[ChatMessage], tools: list[dict]
    ) -> dict:
        """Non-streaming chat that supports tool calling.

        Returns the assistant message. OpenAI-shaped `tool_calls` carry their
        arguments as a JSON *string* where Ollama uses a dict; the caller in
        `routers/chat.py` already accepts either, so the message is returned
        unchanged rather than rewritten into Ollama's shape.
        """
        payload = {
            **self._payload(messages, None),
            "tools": tools,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                if response.status_code >= 400:
                    raise self._fail(response)
                data = response.json()
                if data.get("error"):
                    raise LLMUnavailable(str(data["error"]))
                choices = data.get("choices") or []
                if not choices:
                    return {}
                return choices[0].get("message", {}) or {}
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"OpenRouter request failed: {exc}") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Not available: OpenRouter brokers chat completions, not embeddings.

        `rag.retrieve` catches this and uses BM25 instead, so raising here is
        the supported way to say "no vectors from this provider" — not an
        oversight to be filled in later with a chat model pretending to embed.
        """
        raise NotImplementedError(
            "OpenRouter does not expose an embeddings endpoint. Retrieval falls "
            "back to BM25 keyword search; configure an embedding-capable "
            "provider to restore vector search."
        )
