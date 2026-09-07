"""One-time provisioning of the local ONNX embedding model.

The workbench itself NEVER downloads models at runtime — that is the core
offline/data-sovereignty guarantee. Run this script once, while the machine
has internet, to place Chroma's all-MiniLM-L6-v2 ONNX model into the local
cache. Afterwards every component runs with no network access.

    python backend/scripts/embed_setup.py

After provisioning, the app uses the real semantic embeddings. On a machine
where this step was skipped the app still works fully offline through the
deterministic `hash` embedding provider (EMBEDDINGS_PROVIDER=hash or auto).

The Docker image performs this step automatically at build time.
"""
from __future__ import annotations

import sys
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"
CACHE_FILE = Path.home() / ".cache" / "chroma" / "onnx_models" / MODEL_NAME / "onnx" / "model.onnx"


def main() -> int:
    if CACHE_FILE.is_file():
        print(f"[embed_setup] Model already cached at {CACHE_FILE}")
        print("[embed_setup] Nothing to do — the app is offline-capable now.")
        return 0

    print("[embed_setup] Downloading the ONNX embedding model (one-time)...")
    print(f"[embed_setup] Target cache: {CACHE_FILE}")
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        fn = DefaultEmbeddingFunction()
        # Force Chroma to load (and therefore download) the model once.
        out = fn(["sovereignai model provisioning warm-up"])
        dim = len(out[0]) if out and out[0] is not None else "?"
        print(f"[embed_setup] OK — model ready (embedding dimension: {dim}).")
        print("[embed_setup] The workbench now runs fully offline. No runtime downloads ever occur.")
        return 0
    except Exception as exc:  # noqa: BLE001 - report and exit cleanly
        print(f"[embed_setup] FAILED: {exc}", file=sys.stderr)
        print("[embed_setup] Check your internet connection and retry.", file=sys.stderr)
        print("[embed_setup] The app still works offline via EMBEDDINGS_PROVIDER=hash.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
