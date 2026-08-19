"""Recuperación de contexto para el tutor (RF-4.3): app/tutor/retrieval.py.

Usa el PDF fixture procesado con fakes (mismo patrón que test_pipeline._ingest):
build_context debe incluir SIEMPRE la sección del bloque actual, más bloques de
otras secciones que compartan palabras clave con la pregunta (búsqueda léxica).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"


def _ingest(settings):
    """Procesa el PDF fixture con FakeLLM/FakeTTS y devuelve (doc_id, conn)."""
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


def _blocks_with_sections(conn, doc_id):
    return conn.execute(
        "SELECT b.id, b.section_id, b.text_clean, s.title"
        " FROM blocks b JOIN sections s ON s.id=b.section_id"
        " WHERE b.document_id=? ORDER BY b.idx",
        (doc_id,),
    ).fetchall()


def _rare_word(rows, exclude_section_id):
    """Palabra (>=8 letras) que solo aparece en UNA sección distinta de la actual."""
    sec_words: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        sec_words[r["section_id"]].update(re.findall(r"[a-z]{8,}", r["text_clean"].lower()))
    counts: dict[str, list[int]] = defaultdict(list)
    for sec_id, words in sec_words.items():
        for w in words:
            counts[w].append(sec_id)
    for w in sorted(counts):  # orden determinista
        holders = counts[w]
        if len(holders) == 1 and holders[0] != exclude_section_id:
            return w, holders[0]
    raise AssertionError("el fixture no tiene ninguna palabra exclusiva de una sección")


def test_current_section_blocks_always_included(app_env):
    from app.tutor.retrieval import build_context
    doc_id, conn = _ingest(app_env)

    # Sección de contenido (idx>=1) con varios bloques; bloque actual: el del medio.
    sec = conn.execute(
        "SELECT s.id, s.title, COUNT(b.id) AS n FROM sections s"
        " JOIN blocks b ON b.section_id=s.id"
        " WHERE s.document_id=? AND s.idx>=1 GROUP BY s.id HAVING n>=2"
        " ORDER BY s.idx LIMIT 1",
        (doc_id,),
    ).fetchone()
    sec_blocks = conn.execute(
        "SELECT id FROM blocks WHERE section_id=? ORDER BY idx", (sec["id"],)).fetchall()
    current = sec_blocks[len(sec_blocks) // 2]["id"]

    ctx = build_context(doc_id, "¿de qué habla esta parte?", current, max_chars=30000)
    assert ctx  # devuelve algo

    # RF-4.3 (a): los bloques de la sección actual están SIEMPRE incluidos.
    ids = {c["block_id"] for c in ctx}
    assert {b["id"] for b in sec_blocks} <= ids

    # (d) cada item trae su section_title correcto y texto no vacío.
    for item in ctx:
        row = conn.execute(
            "SELECT s.title, b.text_clean FROM blocks b JOIN sections s ON s.id=b.section_id"
            " WHERE b.id=?",
            (item["block_id"],),
        ).fetchone()
        assert item["section_title"] == row["title"]
        assert item["text"].strip()


def test_question_keyword_pulls_blocks_from_other_section(app_env):
    from app.tutor.retrieval import build_context
    doc_id, conn = _ingest(app_env)
    rows = _blocks_with_sections(conn, doc_id)

    # Bloque actual: el primero de la primera sección de contenido.
    first_content = conn.execute(
        "SELECT id FROM sections WHERE document_id=? AND idx=1", (doc_id,)).fetchone()
    current_block = conn.execute(
        "SELECT id FROM blocks WHERE section_id=? ORDER BY idx LIMIT 1",
        (first_content["id"],),
    ).fetchone()["id"]

    word, target_sec = _rare_word(rows, exclude_section_id=first_content["id"])

    # (b) una palabra rara que solo aparece en otra sección trae bloques de esa sección.
    ctx = build_context(
        doc_id, f"¿qué dice el documento sobre {word}?", current_block, max_chars=30000)
    ctx_secs = {
        conn.execute("SELECT section_id FROM blocks WHERE id=?",
                     (c["block_id"],)).fetchone()["section_id"]
        for c in ctx
    }
    assert target_sec in ctx_secs, f"la palabra {word!r} no trajo su sección"


def test_context_respects_max_chars(app_env):
    from app.tutor.retrieval import build_context
    doc_id, conn = _ingest(app_env)
    current_block = conn.execute(
        "SELECT id FROM blocks WHERE document_id=? ORDER BY idx LIMIT 1",
        (doc_id,),
    ).fetchone()["id"]

    # (c) presupuesto por defecto (8000) y presupuesto pequeño: nunca se supera.
    ctx = build_context(doc_id, "¿cuál es la contribución principal?", current_block)
    assert ctx
    assert sum(len(c["text"]) for c in ctx) <= 8000

    small = build_context(
        doc_id, "¿cuál es la contribución principal?", current_block, max_chars=1500)
    assert small  # incluso con poco presupuesto devuelve algo
    assert sum(len(c["text"]) for c in small) <= 1500
