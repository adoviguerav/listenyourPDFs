"""API del tutor push-to-talk (RF-4.1): POST /api/documents/{id}/ask + eventos /ws.

TestClient + worker en línea + FakeSTT/FakeLLM/FakeTTS. La respuesta streaming
llega por el WebSocket /ws existente (query param doc): answer.delta,
sentence.audio (con url descargable) y answer.done.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"


def _client(app_env):
    from fastapi.testclient import TestClient

    from app.api.main import app
    return TestClient(app)


def _ingest(settings):
    """Procesa el PDF fixture con fakes (patrón de test_pipeline._ingest)."""
    import shutil

    from app import db, worker
    from app.providers.fakes import FakeLLM, FakeTTS
    conn = db.connect()
    dest = settings.data_dir / "pdfs" / FIXTURE.name
    shutil.copy(FIXTURE, dest)
    doc_id = conn.execute(
        "INSERT INTO documents(title, filename) VALUES (?,?)",
        (FIXTURE.stem, dest.name),
    ).lastrowid
    conn.execute(
        "INSERT INTO jobs(type, payload) VALUES ('process_document', ?)",
        (json.dumps({"document_id": doc_id}),),
    )
    worker.run_pending(llm=FakeLLM(), tts=FakeTTS())
    return doc_id, conn


def _stream_llm(section_title):
    """FakeLLM con answer() en streaming que cita una sección real del documento."""
    from app.providers.fakes import FakeLLM

    class StreamLLM(FakeLLM):
        def answer(self, question, context, lang):
            self.calls.append("answer")
            for d in ["La respuesta ", "sale en trozos. ", "Y termina bien.\n",
                      f"FUENTE: {section_title}"]:
                yield d

        answer_stream = answer  # el motor puede usar cualquiera de los dos nombres

    return StreamLLM()


def test_ask_json_streams_answer_and_audio_via_ws(app_env, monkeypatch):
    """(a)+(c) POST /ask JSON → 200 con request_id; por el WS llegan answer.delta,
    al menos un sentence.audio y answer.done; los urls se descargan con 200.

    Bajo A14 el tutor corre EN EL PROCESO API (no en el worker): los fakes se
    inyectan monkeypatcheando el registry que el pipeline resuelve en runtime."""
    from app.providers import registry
    from app.providers.fakes import FakeTTS
    doc_id, conn = _ingest(app_env)
    title = conn.execute(
        "SELECT title FROM sections WHERE document_id=? AND idx=1", (doc_id,)
    ).fetchone()["title"]
    block_id = conn.execute(
        "SELECT id FROM blocks WHERE document_id=? ORDER BY idx LIMIT 1", (doc_id,)
    ).fetchone()["id"]
    llm, tts = _stream_llm(title), FakeTTS()
    monkeypatch.setattr(registry, "get_llm", lambda name=None: llm)
    monkeypatch.setattr(registry, "get_tts", lambda name=None: tts)

    with _client(app_env) as client:
        with client.websocket_connect(f"/ws?doc={doc_id}") as ws:
            r = client.post(
                f"/api/documents/{doc_id}/ask",
                json={"question": "¿de qué va el paper?", "block_id": block_id},
            )
            assert r.status_code == 200
            request_id = r.json()["request_id"]
            assert request_id

            deltas, audios, done = [], [], None
            for _ in range(300):  # tolera doc.status/block.ready intercalados
                msg = ws.receive_json()
                if msg["type"] == "answer.delta":
                    deltas.append(msg)
                elif msg["type"] == "sentence.audio":
                    audios.append(msg)
                elif msg["type"] == "answer.done":
                    done = msg
                    break
            assert deltas, "no llegó ningún answer.delta por el WS"
            # El texto viaja en los deltas (RF-4.1).
            text = "".join(d.get("text") or d.get("text_delta") or "" for d in deltas)
            assert "trozos" in text
            assert audios, "no llegó ningún sentence.audio por el WS"
            assert done is not None

        # (c) el audio de cada frase se sirve por GET normal, como los bloques.
        for ev in audios:
            resp = client.get(ev["url"])
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "audio/mpeg"


def test_ask_multipart_audio_returns_transcript(app_env, monkeypatch):
    """(b) POST /ask multipart con audio → la respuesta incluye el transcript del STT."""
    from app.providers import registry
    from app.providers.fakes import FakeSTT
    doc_id, conn = _ingest(app_env)
    block_id = conn.execute(
        "SELECT id FROM blocks WHERE document_id=? ORDER BY idx LIMIT 1", (doc_id,)
    ).fetchone()["id"]

    stt = FakeSTT(text="¿qué dice el abstract?")
    # La API resuelve el STT vía registry.get_stt (RF-7.4): inyectamos el fake configurado.
    monkeypatch.setattr(registry, "get_stt", lambda name=None: stt)

    with _client(app_env) as client:
        r = client.post(
            f"/api/documents/{doc_id}/ask",
            data={"block_id": str(block_id)},
            files={"audio": ("pregunta.webm", b"\x1aE\xdf\xa3audio-falso", "audio/webm")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["transcript"] == "¿qué dice el abstract?"  # RF-4.1: pausa→STT→…
        assert body["request_id"]
        assert len(stt.calls) == 1  # el audio pasó por el STT exactamente una vez


def test_ask_requires_token(app_env, monkeypatch):
    """(d) auth: con LYP_TOKEN seteado, /ask sin token → 401 (como el resto de la API)."""
    monkeypatch.setattr("app.config.settings.auth_token", "secreto")
    with _client(app_env) as client:
        r = client.post("/api/documents/1/ask",
                        json={"question": "hola", "block_id": 1})
        assert r.status_code == 401
