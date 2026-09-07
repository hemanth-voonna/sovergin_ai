"""API endpoint tests."""
from __future__ import annotations

from pathlib import Path

from app.config import settings

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "services" in body


def test_upload_list_get_delete(client):
    with open(SAMPLES / "land_record.txt", "rb") as fh:
        r = client.post("/api/documents/upload", files={"file": ("doc.txt", fh, "text/plain")})
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "uploaded"
    assert doc["file_type"] == "txt"

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    assert any(d["id"] == doc["id"] for d in listing.json()["items"])

    detail = client.get(f"/api/documents/{doc['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == doc["id"]

    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/documents/{doc['id']}").status_code == 404


def test_upload_rejects_fake_pdf(client):
    fake = b"this is not a pdf at all"
    r = client.post("/api/documents/upload", files={"file": ("fake.pdf", fake, "application/pdf")})
    assert r.status_code == 400
    assert "magic" in r.json()["detail"].lower() or "content" in r.json()["detail"].lower()


def test_upload_rejects_bad_extension(client):
    r = client.post("/api/documents/upload", files={"file": ("evil.exe", b"MZ....", "application/octet-stream")})
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"]


def test_upload_rejects_empty(client):
    r = client.post("/api/documents/upload", files={"file": ("empty.txt", b"", "text/plain")})
    assert r.status_code == 400


def test_full_pipeline_via_api(client):
    with open(SAMPLES / "land_record.txt", "rb") as fh:
        r = client.post("/api/documents/upload", files={"file": ("lr.txt", fh, "text/plain")})
    doc_id = r.json()["id"]

    assert client.post(f"/api/documents/{doc_id}/process").json()["status"] == "processed"
    indexed = client.post(f"/api/documents/{doc_id}/index").json()
    assert indexed["status"] == "indexed"
    assert indexed["chunk_count"] > 0

    ans = client.post("/api/rag/query", json={"question": "Who is the registered owner?"}).json()
    assert ans["grounded"] is True
    assert "Sunita" in ans["answer"]
    assert len(ans["sources"]) > 0

    val = client.post("/api/validation/check", json={"document_id": doc_id}).json()
    assert val["status"] == "valid"

    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    # vectors removed with the document
    ans2 = client.post("/api/rag/query", json={"question": "Who is the registered owner?"}).json()
    assert all(s["document_id"] != doc_id for s in ans2["sources"])


def test_rag_query_validation(client):
    assert client.post("/api/rag/query", json={"question": ""}).status_code == 422
    assert client.post("/api/rag/query", json={}).status_code == 422


def test_sample_endpoint(client):
    r = client.post("/api/documents/sample")
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert r.json()["original_name"] == "land_record_sample.txt"
    client.delete(f"/api/documents/{doc_id}")


def test_agents_endpoints(client):
    agents = client.get("/api/agents")
    assert agents.status_code == 200
    assert len(agents.json()) == 5

    detail = client.get("/api/agents/task")
    assert detail.status_code == 200
    assert detail.json()["id"] == "task"

    r = client.post("/api/agents/run", json={"agent_id": "task", "inputs": {"prompt": "do something"}})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_validation_endpoint_requires_document(client):
    assert client.post("/api/validation/check", json={}).status_code == 400
    assert client.post("/api/validation/check", json={"document_id": "missing"}).status_code == 404


def test_sandbox_endpoint(client):
    r = client.post("/api/sandbox/run", json={"code": "print('api sandbox')", "language": "python"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert "api sandbox" in body["stdout"]
    assert body["log"]


def test_ocr_endpoint_rejects_non_image(client):
    with open(SAMPLES / "land_record.txt", "rb") as fh:
        r = client.post("/api/ocr/process", files={"file": ("lr.txt", fh, "text/plain")})
    assert r.status_code in (400, 503)  # 400 for txt type, 503 if no tesseract


def test_ocr_endpoint_document_id_param(client, sample_doc_id):
    # without tesseract we expect 503; with tesseract the corpus PNG is OCR'd
    r = client.post(f"/api/ocr/process?document_id={sample_doc_id}")
    assert r.status_code in (503, 400)  # txt doc unsupported for OCR / no tesseract


def test_ocr_endpoint_requires_source(client):
    r = client.post("/api/ocr/process")
    assert r.status_code == 400


def test_dashboard(client, sample_doc_id):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["documents"]["total"] >= 1
    assert body["documents"]["indexed"] >= 1
    assert body["vectors_indexed"] >= 1
    assert body["recent_activity"]
    assert len(body["activity_series"]) == 7


def test_settings_no_secrets(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "api_key" not in body and "token" not in json_lower(body)
    assert body["llm_provider"] == "mock"


def json_lower(body: dict) -> str:
    import json

    return json.dumps(body).lower()


def test_optional_auth_token(monkeypatch, client):
    """When ACCESS_TOKEN is set, requests without it are rejected."""
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "s3cr3t")
    try:
        assert client.get("/api/health").status_code == 200  # health exempt
        assert client.get("/api/documents").status_code == 401
        assert client.get("/api/documents", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/api/documents", headers={"Authorization": "Bearer s3cr3t"}).status_code == 200
    finally:
        monkeypatch.undo()