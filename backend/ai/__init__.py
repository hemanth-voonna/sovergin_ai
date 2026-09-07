"""AI layer: configurable LLM clients and local embedding providers."""

from .embeddings import EmbeddingService, get_embedding_service
from .llm import LLMClient, MockGroundedLLM, OpenAICompatibleLLM, get_llm

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "LLMClient",
    "MockGroundedLLM",
    "OpenAICompatibleLLM",
    "get_llm",
]