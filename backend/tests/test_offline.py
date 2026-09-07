"""Tests for the strict LOCAL-ONLY / OFFLINE guarantees.

These lock in three properties:
  1. No cloud AI endpoint can ever be selected (api.openai.com & co are refused
     unless the operator explicitly opts into remote hosts).
  2. An API key alone never enables a cloud provider (a local base URL is
     required).
  3. Embeddings never download at runtime: if the ONNX model is not cached the
     service silently uses the deterministic hash provider.
  4. Chroma product telemetry is disabled.
"""
from __future__ import annotations

import os

import pytest

import app.config as cfg
from ai.embeddings import EmbeddingService
from ai.llm import MockGroundedLLM, OpenAICompatibleLLM, resolve_llm
from rag.vectorstore import get_vector_store


def test_telemetry_env_set_before_chroma_import():
    # app.config is imported first by every module; it must flip the switch.
    assert os.environ.get("ANONYMIZED_TELEMETRY", "").strip().lower() == "false"


def test_vectorstore_telemetry_disabled():
    store = get_vector_store()
    client = getattr(store, "_client", None)
    if client is not None:  # chroma backend
        assert client._system.settings.anonymized_telemetry is False


def test_default_llm_is_offline_builtin():
    assert isinstance(resolve_llm(), MockGroundedLLM)


def test_api_key_alone_never_enables_cloud(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(s, "OPENAI_API_KEY", "sk-leaked-cloud-key")
    monkeypatch.setattr(s, "OPENAI_BASE_URL", "")
    monkeypatch.setattr(s, "ALLOW_REMOTE_LLM", False)
    llm = resolve_llm()
    assert isinstance(llm, MockGroundedLLM)
    assert not isinstance(llm, OpenAICompatibleLLM)


@pytest.mark.parametrize(
    "base_url",
    ["", "https://api.openai.com/v1", "https://generativelanguage.googleapis.com/v1"],
)
def test_remote_or_missing_endpoints_refused(monkeypatch, base_url):
    s = cfg.settings
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(s, "OPENAI_BASE_URL", base_url)
    monkeypatch.setattr(s, "ALLOW_REMOTE_LLM", False)
    assert isinstance(resolve_llm(), MockGroundedLLM)


def test_loopback_endpoint_allowed(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai-compatible")
    monkeypatch.setattr(s, "OPENAI_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.setattr(s, "ALLOW_REMOTE_LLM", False)
    llm = resolve_llm()
    assert isinstance(llm, OpenAICompatibleLLM)


def test_remote_endpoint_allowed_only_with_opt_in(monkeypatch):
    s = cfg.settings
    monkeypatch.setattr(s, "LLM_PROVIDER", "openai-compatible")
    monkeypatch.setattr(s, "OPENAI_BASE_URL", "http://192.168.1.50:8000/v1")
    monkeypatch.setattr(s, "ALLOW_REMOTE_LLM", True)  # explicit opt-in
    llm = resolve_llm()
    assert isinstance(llm, OpenAICompatibleLLM)


def test_embeddings_fallback_when_model_not_cached(monkeypatch):
    monkeypatch.setattr("ai.embeddings._onnx_model_cached", lambda: False)
    svc = EmbeddingService(provider="auto")
    out = svc.embed_texts(["offline-only machine"])
    assert len(out[0]) == 384
    assert svc.fallback_used is True
    assert svc.provider_name == "hash (fallback)"


def test_hash_provider_needs_no_model_or_network():
    from ai.embeddings import HashEmbeddingProvider

    provider = HashEmbeddingProvider()
    vecs = provider.embed_texts(["village kamalpur survey 123"])
    assert len(vecs[0]) == provider.dim
