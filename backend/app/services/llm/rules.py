"""Deterministic fallback used when Ollama is not running.

It does not pretend to be a model. It answers from the retrieved concept notes
and from the learner's own plan, and the API flags the response as `degraded`
so the UI can say so honestly instead of showing the prototype's opaque
"Sorry, I'm offline right now."
"""

from __future__ import annotations

import re
from typing import AsyncIterator

from app.services.llm.base import ChatMessage


class RetrievalOnlyProvider:
    """Formats retrieved context into a useful answer without generating text."""

    async def is_available(self) -> bool:
        return True

    async def stream_chat(
        self, messages: list[ChatMessage], options: dict | None = None
    ) -> AsyncIterator[str]:
        yield self.answer(messages)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Embeddings need a model; run Ollama and re-seed with --embed."
        )

    @staticmethod
    def answer(messages: list[ChatMessage], *, public: bool = False) -> str:
        """Assemble an answer from the retrieved notes alone.

        ``public`` changes only the wording. An anonymous visitor on the
        landing page is not the person who can start Ollama, so telling them to
        run ``ollama serve`` would be noise dressed up as help.
        """
        question = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        context = next((m["content"] for m in messages if m["role"] == "system"), "")

        excerpts = _extract_excerpts(context)
        subject = "The AI helper" if public else "The AI tutor"

        if not excerpts:
            if public:
                return (
                    f"{subject} is offline right now, so I cannot generate an "
                    "answer — and nothing in the SkillAtlas material matched "
                    "that question. Try naming a topic, or browse the tracks "
                    "from the home page."
                )
            return (
                f"{subject} is offline, and I could not find anything in your "
                "course notes that matches that question. Try naming a concept "
                "from your roadmap — for example \"what is caching for?\"."
            )

        whose = "the course notes" if public else "your notes"
        lines = [
            f"{subject} is offline, so here is the relevant material from "
            f"{whose} rather than a generated answer.",
            "",
        ]
        for title, body in excerpts[:3]:
            lines.append(f"**{title}**")
            lines.append(_first_sentences(body, 3))
            lines.append("")

        if question and not public:
            lines.append(
                "Start Ollama (`ollama serve`) and ask again for a direct answer."
            )
        return "\n".join(lines).strip()


def _extract_excerpts(context: str) -> list[tuple[str, str]]:
    """Pull the `### <title>` blocks the chat router builds into the prompt."""
    blocks = re.split(r"^### ", context, flags=re.MULTILINE)[1:]
    excerpts: list[tuple[str, str]] = []
    for block in blocks:
        title, _, body = block.partition("\n")
        if body.strip():
            excerpts.append((title.strip(), body.strip()))
    return excerpts


def _first_sentences(text: str, count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    return " ".join(sentences[:count]).strip()
