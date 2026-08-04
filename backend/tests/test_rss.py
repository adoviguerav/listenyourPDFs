"""RSS (RF-7.6), QR (RF-7.5) y WebSocket (A4)."""
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"


def _client():
    from fastapi.testclient import TestClient

    from app.api.main import app
    return TestClient(app)


def _upload_and_process(client, worker, llm, tts):
    r = client.post("/api/documents",
                    files={"file": ("paper.pdf", FIXTURE.read_bytes(), "application/pdf")})
    doc_id = r.json()["id"]
    worker.run_pending(llm=llm, tts=tts)
    return doc_id


def test_publish_rss_full_flow(app_env):
    from app import worker
    from app.providers.espeak_tts import EspeakTTS
    from app.providers.fakes import FakeLLM
    llm, tts = FakeLLM(), EspeakTTS()

    import app.config as config
    config.settings.warmup_blocks = 2  # doc pequeño para el test

    with _client() as client:
        doc_id = _upload_and_process(client, worker, llm, tts)

        r = client.post(f"/api/documents/{doc_id}/publish-rss")
        assert r.status_code == 202

        # Varias vueltas: síntesis restante + concat (que espera a los bloques).
        for _ in range(5):
            worker.run_pending(llm=llm, tts=tts)
            doc = client.get(f"/api/documents/{doc_id}").json()
            if doc.get("full_mp3_path"):
                break
        assert doc["full_mp3_path"], "el MP3 completo no se generó"
        assert (app_env.data_dir / doc["full_mp3_path"]).stat().st_size > 10000

        # Feed RSS válido con el episodio y enclosure.
        xml = client.get("/feed.xml").text
        root = ET.fromstring(xml)  # parsea o revienta
        items = root.findall("./channel/item")
        assert len(items) == 1
        enc = items[0].find("enclosure")
        assert enc.get("type") == "audio/mpeg"
        assert f"/audio/{doc_id}.mp3" in enc.get("url")
        assert int(enc.get("length")) > 10000

        # El MP3 del episodio se sirve.
        r = client.get(f"/audio/{doc_id}.mp3")
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


def test_feed_and_audio_require_token(app_env, monkeypatch):
    monkeypatch.setattr("app.config.settings.auth_token", "secreto")
    with _client() as client:
        assert client.get("/feed.xml").status_code == 401
        assert client.get("/feed.xml", params={"token": "secreto"}).status_code == 200
        assert client.get("/audio/1.mp3").status_code == 401


def test_qr_endpoint(app_env):
    with _client() as client:
        r = client.get("/api/qr")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg")
        assert "<svg" in r.text


def test_websocket_block_ready(app_env):
    from app import worker
    from app.providers.fakes import FakeLLM, FakeTTS
    llm, tts = FakeLLM(), FakeTTS()
    with _client() as client:
        doc_id = _upload_and_process(client, worker, llm, tts)
        with client.websocket_connect(f"/ws?doc={doc_id}") as ws:
            got_status, got_block = False, False
            for _ in range(12):
                msg = ws.receive_json()
                got_status |= msg["type"] == "doc.status" and msg["status"] == "ready"
                got_block |= msg["type"] == "block.ready"
                if got_status and got_block:
                    break
            assert got_status and got_block
