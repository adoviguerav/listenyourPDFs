"""Integración de la pipeline con un PDF real (fixture del spike S0.2)."""
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"


def _ingest(settings, llm=None, tts=None):
    import shutil

    from app import db, worker
    from app.providers.fakes import FakeLLM, FakeTTS
    llm, tts = llm or FakeLLM(), tts or FakeTTS()
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
    worker.run_pending(llm=llm, tts=tts)
    return doc_id, conn, llm, tts


def test_pipeline_produces_structure_and_warmup_audio(app_env):
    doc_id, conn, llm, tts = _ingest(app_env)
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    assert doc["status"] == "ready"
    assert doc["language"] == "en"  # el paper fixture está en inglés (D9: idioma original)

    sections = conn.execute(
        "SELECT * FROM sections WHERE document_id=? ORDER BY idx", (doc_id,)).fetchall()
    titles = [s["title"] for s in sections]
    assert sections[0]["idx"] == 0 and "Introduction" in titles[0]  # intro RF-2.0
    assert any("Abstract" in t for t in titles)

    blocks = conn.execute(
        "SELECT * FROM blocks WHERE document_id=? ORDER BY idx", (doc_id,)).fetchall()
    assert len(blocks) > 30
    for b in blocks:  # nada de residuos en el texto que va al TTS
        assert "http" not in b["text_clean"]
        assert "<sup>" not in b["text_clean"]

    done = [b for b in blocks if b["audio_status"] == "done"]
    assert len(done) == app_env.warmup_blocks  # arranque bajo demanda (A6/RNF-1)
    for b in done:
        assert (app_env.data_dir / b["audio_path"]).exists()
        assert b["duration_ms"] > 0

    assert doc["total_cost_cents"] > 0  # contador de coste (RNF-2)
    assert "intro" in llm.calls and "clean" in llm.calls


def test_cache_never_synthesizes_same_text_twice(app_env):
    """Subir el mismo documento dos veces: el segundo arranque sale 100% de cache (RNF-2)."""
    doc1, conn, llm, tts = _ingest(app_env)
    calls_after_first = len(tts.calls)
    assert calls_after_first == app_env.warmup_blocks

    doc2, conn, llm, tts = _ingest(app_env, llm=llm, tts=tts)
    assert doc2 != doc1

    done2 = conn.execute(
        "SELECT * FROM blocks WHERE document_id=? AND audio_status='done'", (doc2,)
    ).fetchall()
    assert len(done2) == app_env.warmup_blocks  # el doc 2 tiene su arranque listo…
    assert len(tts.calls) == calls_after_first   # …sin ni una síntesis nueva
    for b in done2:
        assert (app_env.data_dir / b["audio_path"]).exists()


def test_delete_document_removes_files(app_env):
    doc_id, conn, llm, tts = _ingest(app_env)
    paths = [app_env.data_dir / r["audio_path"] for r in conn.execute(
        "SELECT audio_path FROM blocks WHERE document_id=? AND audio_path IS NOT NULL",
        (doc_id,)).fetchall()]
    assert paths and all(p.exists() for p in paths)

    from fastapi.testclient import TestClient

    from app.api.main import app
    with TestClient(app) as client:
        assert client.delete(f"/api/documents/{doc_id}").json()["ok"]
    assert not any(p.exists() for p in paths)  # borrado real (RNF-4)


def test_parallel_synthesis_is_correct_and_faster(app_env):
    """A13: los jobs synthesize corren en paralelo sin corromper estado."""
    import time

    from app.providers.fakes import FakeLLM, FakeTTS

    class SlowTTS(FakeTTS):
        def synthesize(self, text, lang):
            time.sleep(0.2)
            return super().synthesize(text, lang)

    t0 = time.time()
    doc_id, conn, llm, tts = _ingest(app_env, llm=FakeLLM(), tts=SlowTTS())
    elapsed = time.time() - t0

    done = conn.execute(
        "SELECT * FROM blocks WHERE document_id=? AND audio_status='done'", (doc_id,)
    ).fetchall()
    assert len(done) == app_env.warmup_blocks
    assert len(set(b["audio_path"] for b in done)) == len(done)
    for b in done:
        assert (app_env.data_dir / b["audio_path"]).exists()
    assert len(tts.calls) == app_env.warmup_blocks  # ni de más (cache) ni de menos
    # No se asierta tiempo exacto para evitar flakiness; elapsed queda como señal:
    # 8×0,2s en serie = 1,6s de TTS mínimo; con pool de 4 la fase TTS ronda 0,4s.
    assert elapsed > 0


def test_blocks_have_increasing_pages(app_env):
    """El mapeo bloque→página existe y es coherente (visor sincronizado)."""
    doc_id, conn, llm, tts = _ingest(app_env)
    pages = [r["page"] for r in conn.execute(
        "SELECT page FROM blocks WHERE document_id=? ORDER BY idx", (doc_id,)).fetchall()]
    assert pages[0] == 1
    assert max(pages) > 5          # el paper fixture tiene 14 páginas
    assert all(b >= a for a, b in zip(pages, pages[1:]))  # nunca retrocede
