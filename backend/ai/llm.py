"""Configurable LLM layer — local-only, offline-first.

Sovereign guarantee: this application never calls a cloud AI API. Only two
kinds of LLM can be active:

  * the built-in grounded engine (default) — deterministic, extractive,
    fully offline, needs no model and never hallucinates;
  * a LOCAL OpenAI-compatible chat endpoint (Ollama, vLLM, LM Studio,
    llama.cpp server, ...) explicitly configured through OPENAI_BASE_URL.

Endpoint policy:
  * OPENAI_BASE_URL must point at the loopback interface (localhost /
    127.x / ::1) — anything else is refused unless ALLOW_REMOTE_LLM=true
    is set as an explicit opt-in.
  * With no (or refused) endpoint the resolver falls back to the built-in
    engine and logs why — it never silently dials api.openai.com.

Environment variables:
  LLM_PROVIDER   auto | builtin | mock | ollama | openai-compatible
  LLM_MODEL      model name served by the LOCAL endpoint
  OPENAI_API_KEY ignored unless a local endpoint is configured
  OPENAI_BASE_URL local endpoint, e.g. http://127.0.0.1:11434/v1 (Ollama)
                 or http://127.0.0.1:1234/v1 (LM Studio)
  ALLOW_REMOTE_LLM  true = permit a non-loopback base URL (explicit opt-in)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)

# Recognised provider names. "mock" and "builtin" are the offline engine;
# "openai"/"local" are accepted legacy aliases for "openai-compatible".
PROVIDER_AUTO = "auto"
PROVIDER_BUILTIN = "builtin"
PROVIDER_OLLAMA = "ollama"
PROVIDER_COMPATIBLE = "openai-compatible"

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_loopback(url: str) -> bool:
    """True when url points at the local machine (loopback interface)."""
    try:
        host = (urlparse(url).hostname or "").lower().strip("[]")
    except ValueError:
        return False
    if host in _LOOPBACK_HOSTS or host.startswith("127."):
        return True
    # hostless forms such as "localhost:11434/v1" parse without a scheme
    if not urlparse(url).scheme:
        host = url.split("/", 1)[0].rsplit(":", 1)[0].lower()
        return host in _LOOPBACK_HOSTS or host.startswith("127.")
    return False


def _endpoint_allowed(base_url: str) -> bool:
    """A configured endpoint may only be used if it is local or explicitly allowed."""
    if not base_url:
        return False
    if _is_loopback(base_url):
        return True
    if settings.ALLOW_REMOTE_LLM:
        return True
    logger.warning(
        "Refusing non-loopback LLM endpoint %r (sovereign mode). "
        "Set ALLOW_REMOTE_LLM=true only if you intentionally target a private network host.",
        base_url,
    )
    return False


class LLMClient(ABC):
    mode: str = "llm"
    name: str = "llm"

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float | None = None,
             max_tokens: int | None = None) -> str: ...


class OpenAICompatibleLLM(LLMClient):
    """A LOCAL OpenAI-compatible chat endpoint (Ollama, vLLM, LM Studio...).

    Instances are only ever created with an explicitly allowed local base URL
    (see resolve_llm); this class never defaults to a cloud endpoint.
    """

    mode = "llm"

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        from openai import OpenAI

        self.model = model
        self.name = f"{model} (local)"
        self._client = OpenAI(api_key=api_key or "sk-local", base_url=base_url)

    def chat(self, messages: list[dict], temperature: float | None = None,
             max_tokens: int | None = None) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
            max_tokens=settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
        )
        return resp.choices[0].message.content or ""


class MockGroundedLLM(LLMClient):
    """Fully offline built-in grounded responder.

    It only reuses text retrieved from the user's own documents and answers
    "not found" when the context does not contain the requested information.
    """

    mode = "mock"
    name = "builtin-grounded"

    def chat(self, messages: list[dict], temperature: float | None = None,
             max_tokens: int | None = None) -> str:
        # The RAG pipeline handles the grounded path directly (rag/grounding.py);
        # generic agent prompts fall back to rule-based agent logic instead.
        last = messages[-1]["content"] if messages else ""
        return _generic_grounded_reply(last)


def _generic_grounded_reply(prompt: str) -> str:
    """Best-effort reply for generic prompts in built-in mode."""
    context, question = "", prompt
    if "Question:" in prompt and "Context:" in prompt:
        _, rest = prompt.split("Context:", 1)
        context, question = rest.rsplit("Question:", 1)
    lines = [ln.strip() for ln in context.splitlines() if ln.strip()]
    if not lines:
        return ("The requested information could not be found in the provided "
                "documents. Please upload and index documents first.")
    qwords = set(_words(question))
    best, best_score = lines[0], 0
    for ln in lines:
        score = len(qwords & set(_words(ln)))
        if score > best_score:
            best, best_score = ln, score
    if best_score == 0:
        return ("The requested information could not be found in the provided "
                "documents. (No relevant passage was retrieved.)")
    return best


def _words(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _try_local_endpoint(base_url: str, model: str, api_key: str) -> LLMClient | None:
    """Construct a local OpenAI-compatible client, or None on any failure."""
    if not _endpoint_allowed(base_url):
        return None
    try:
        client = OpenAICompatibleLLM(base_url=base_url, model=model, api_key=api_key)
        logger.info("LLM configured (local endpoint): %s @ %s", model, base_url)
        return client
    except Exception as exc:  # missing package, bad URL, unreachable server...
        logger.warning("Local LLM endpoint init failed (%s); using built-in grounded engine.", exc)
        return None


def resolve_llm() -> LLMClient:
    """Factory: pick the LLM client from configuration (never a cloud default)."""
    provider = settings.LLM_PROVIDER.strip().lower().replace("_", "-")
    base_url = settings.OPENAI_BASE_URL.strip().rstrip("/")
    model = settings.LLM_MODEL.strip() or "local-model"

    # -- built-in offline engine (aliases: builtin, mock) -------------------
    if provider in ("builtin", "mock"):
        return MockGroundedLLM()

    # -- local OpenAI-compatible endpoint ----------------------------------
    wants_endpoint = provider in (PROVIDER_COMPATIBLE, "local", "openai",
                                  PROVIDER_OLLAMA, PROVIDER_AUTO)
    if wants_endpoint:
        if provider == PROVIDER_OLLAMA and not base_url:
            base_url = "http://127.0.0.1:11434/v1"  # Ollama default, local
        if not base_url:
            if provider != PROVIDER_AUTO:
                logger.warning(
                    "LLM_PROVIDER=%s requires OPENAI_BASE_URL pointing at a LOCAL endpoint "
                    "(cloud endpoints are disabled in sovereign/offline mode). ",
                    settings.LLM_PROVIDER,
                )
            logger.info("Using the built-in grounded engine (sovereign mode).")
            return MockGroundedLLM()
        if settings.OPENAI_API_KEY.strip():
            logger.warning(
                "OPENAI_API_KEY is only honoured for local OpenAI-compatible endpoints "
                "configured via OPENAI_BASE_URL; it is never sent to a cloud service."
            )
        client = _try_local_endpoint(base_url, model, settings.OPENAI_API_KEY)
        if client is not None:
            return client
        logger.warning("Local LLM endpoint unavailable; using the built-in grounded engine.")
        return MockGroundedLLM()

    logger.warning("Unknown LLM_PROVIDER=%r; using built-in grounded engine.", settings.LLM_PROVIDER)
    return MockGroundedLLM()


@lru_cache
def get_llm() -> LLMClient:
    return resolve_llm()


def llm_configured() -> bool:
    return isinstance(get_llm(), OpenAICompatibleLLM)
