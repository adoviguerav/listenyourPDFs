"""API: subir → procesar (worker en línea) → playlist → audio → posición → coste."""
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"


def _client(app_env):
    from fastapi.testclient import TestClient

    from app.api.main import app
    return TestClient(app)


def test_full_flow(app_env):
    from app import worker
    from app.providers.fakes import FakeLLM, FakeTTS
    llm, tts = FakeLLM(), FakeTTS()

    with _client(app_env) as client:
        r = client.post("/api/documents",
                        files={"file": ("paper.pdf", FIXTURE.read_bytes(), "application/pdf")})
        assert r.status_code == 202
        doc_id = r.json()["id"]

        worker.run_pending(llm=llm, tts=tts)

        doc = client.get(f"/api/documents/{doc_id}").json()
        assert doc["status"] == "ready"
        assert doc["sections"][0]["idx"] == 0
        playlist = doc["playlist"]
        assert len(playlist) > 30

        done = [b for b in playlist if b["audio_status"] == "done"]
        r = client.get(f"/api/documents/{doc_id}/blocks/{done[0]['id']}/audio")
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"

        cold = next(b for b in playlist if b["audio_status"] == "pending")
        r = client.get(f"/api/documents/{doc_id}/blocks/{cold['id']}/audio")
        assert r.status_code == 202  # se encola con prioridad (A6)
        worker.run_pending(llm=llm, tts=tts)
        r = client.get(f"/api/documents/{doc_id}/blocks/{cold['id']}/audio")
        assert r.status_code == 200

        r = client.post(f"/api/documents/{doc_id}/position",
                        json={"block_id": cold["id"], "offset_ms": 1500})
        assert r.json()["ok"]
        worker.run_pending(llm=llm, tts=tts)  # colchón por delante de la posición
        lst = client.get("/api/documents").json()
        assert lst[0]["position_idx"] == cold["idx"]

        costs = client.get("/api/costs").json()
        assert costs["month_cents"] > 0
        assert costs["documents"][0]["total_cost_cents"] > 0


def test_auth_token(app_env, monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_token", "secreto")
    with _client(app_env) as client:
        assert client.get("/api/documents").status_code == 401
        assert client.get("/api/documents",
                          headers={"Authorization": "Bearer secreto"}).status_code == 200
        assert client.get("/api/documents", params={"token": "secreto"}).status_code == 200


def test_rejects_non_pdf(app_env):
    with _client(app_env) as client:
        r = client.post("/api/documents", files={"file": ("nota.txt", b"hola", "text/plain")})
        assert r.status_code == 400
