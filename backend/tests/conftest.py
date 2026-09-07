"""Test configuration.

Sets up a hermetic environment BEFORE the app modules are imported:
hash embeddings (fast + deterministic), mock LLM, SQLite + temp dirs.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

_TMP = tempfile.mkdtemp(prefix="sovereignai-test-")

os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
        "DATA_DIR": f"{_TMP}/data",
        "UPLOAD_DIR": f"{_TMP}/uploads",
        "VECTOR_DB_PATH": f"{_TMP}/chroma",
        "SAMPLE_DIR": str(BACKEND_ROOT / "samples"),
        "EMBEDDINGS_PROVIDER": "hash",
        "EMBEDDING_MODEL": "test-model",
        "LLM_PROVIDER": "mock",
        "OPENAI_API_KEY": "",
        "ENV": "test",
        "LOG_LEVEL": "WARNING",
        "ACCESS_TOKEN": "",
        "SANDBOX_TIMEOUT_SECONDS": "10",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sample_doc_id(client) -> str:
    """Upload + process + index the clean sample document. Returns its id."""
    with open(Path(settings.SAMPLE_DIR) / "land_record.txt", "rb") as fh:
        r = client.post("/api/documents/upload", files={"file": ("land_record.txt", fh, "text/plain")})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert client.post(f"/api/documents/{doc_id}/process").status_code == 200
    assert client.post(f"/api/documents/{doc_id}/index").status_code == 200
    return doc_id


@pytest.fixture(scope="session")
def issues_doc_id(client) -> str:
    """Upload + process the sample document that contains validation issues."""
    with open(Path(settings.SAMPLE_DIR) / "land_record_with_issues.txt", "rb") as fh:
        r = client.post(
            "/api/documents/upload",
            files={"file": ("land_record_with_issues.txt", fh, "text/plain")},
        )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert client.post(f"/api/documents/{doc_id}/process").status_code == 200
    return doc_id


@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    yield
    shutil.rmtree(_TMP, ignore_errors=True)