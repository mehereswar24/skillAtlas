"""Local Ollama provider.

Chat runs on ``qwen2.5:7b`` and embeddings on ``nomic-embed-text`` — both
already installed. Nothing leaves the machine and there are no quotas.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.config import settings
from app.services.llm.base import ChatMessage, LLMUnavailable


class OllamaProvider:
    def __init__(
        self,
        base_url: str | None = None,
        chat_model: str | None = None,
        embed_model: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.chat_model = chat_model or settings.ollama_chat_model
        self.embed_model = embed_model or settings.ollama_embed_model
        self.timeout = timeout or settings.ollama_timeout_sec

    async def is_available(self) -> bool:
        """True when Ollama is up and the chat model is pulled."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                installed = {
                    model.get("name", "") for model in response.json().get("models", [])
                }
        except (httpx.HTTPError, ValueError):
            return False

        # Ollama reports "qwen2.5:7b"; accept a bare name without the tag too.
        return any(
            name == self.chat_model or name.split(":")[0] == self.chat_model.split(":")[0]
            for name in installed
        )

    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "stream": True,
            "options": {
                # Low temperature: this is a tutor grounded in supplied notes,
                # not a creative writer.
                "temperature": 0.3,
                "num_ctx": 8192,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("error"):
                            raise LLMUnavailable(str(chunk["error"]))
                        fragment = chunk.get("message", {}).get("content", "")
                        if fragment:
                            yield fragment
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Ollama request failed: {exc}") from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.embed_model, "input": texts},
                )
                if response.status_code == 404:
                    # Older Ollama builds only expose /api/embeddings, which
                    # takes a single prompt at a time.
                    return [await self._embed_one(client, text) for text in texts]
                response.raise_for_status()
                return response.json()["embeddings"]
        except (httpx.HTTPError, KeyError) as exc:
            raise LLMUnavailable(f"Ollama embedding failed: {exc}") from exc

    async def _embed_one(self, client: httpx.AsyncClient, text: str) -> list[float]:
        response = await client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.embed_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]
