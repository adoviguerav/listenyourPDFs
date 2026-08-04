"""Orquestación de la pipeline: extract → clean → bloques → intro → síntesis.

La síntesis usa cache por hash de texto (RNF-2): un mismo texto nunca se
sintetiza dos veces, ni dentro de un documento ni entre documentos.
"""
import hashlib
import json

from ..config import settings
from ..db import connect
from ..providers.base import LLMProvider, TTSProvider
from .blocks import split_into_blocks
from .clean import clean_paragraph, is_table_junk
from .extract import extract


def text_hash(text: str, tts_name: str, lang: str) -> str:
    return hashlib.sha256(f"{tts_name}:{lang}:{text}".encode()).hexdigest()[:32]


def process_document(doc_id: int, llm: LLMProvider, use_llm_clean: bool = True) -> None:
    """Job `process_document`: deja el documento con estructura + bloques y encola el arranque."""
    conn = connect()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    pdf_path = settings.data_dir / "pdfs" / doc["filename"]
    conn.execute("UPDATE documents SET status='extracting' WHERE id=?", (doc_id,))

    structure = extract(pdf_path)
    lang = structure.language
    conn.execute(
        "UPDATE documents SET title=?, language=? WHERE id=?",
        (structure.title, lang, doc_id),
    )

    # Intro de 60s (RF-2.0) como sección idx=0.
    try:
        intro_text = llm.intro(structure.outline(), structure.title, lang)
        _track_cost(conn, doc_id, "llm", len(intro_text))
    except Exception:
        intro_text = ""

    block_idx = 0
    if intro_text:
        sec_id = conn.execute(
            "INSERT INTO sections(document_id, idx, title) VALUES (?,0,?)",
            (doc_id, "Introducción" if lang == "es" else "Introduction"),
        ).lastrowid
        block_idx = _insert_blocks(conn, doc_id, sec_id, [(intro_text, 1)], lang, block_idx)

    for s_idx, section in enumerate(structure.sections, start=1):
        cleaned: list[tuple[str, int]] = []
        for p in section.paragraphs:
            if is_table_junk(p.text):
                continue
            c = clean_paragraph(p.text)
            if not c:
                continue
            if use_llm_clean:
                try:
                    c = llm.clean_block(c, structure.title, lang).text
                    _track_cost(conn, doc_id, "llm", len(c))
                except Exception:
                    pass  # la limpieza heurística ya es escuchable
            cleaned.append((c, p.page))
        blocks = split_into_blocks(cleaned)
        if not blocks:
            continue
        sec_id = conn.execute(
            "INSERT INTO sections(document_id, idx, title) VALUES (?,?,?)",
            (doc_id, s_idx, section.title),
        ).lastrowid
        block_idx = _insert_blocks(conn, doc_id, sec_id, blocks, lang, block_idx)

    conn.execute("UPDATE documents SET status='ready' WHERE id=?", (doc_id,))
    # Arranque (RNF-1): sintetizar los primeros N bloques con prioridad alta.
    rows = conn.execute(
        "SELECT id FROM blocks WHERE document_id=? ORDER BY idx LIMIT ?",
        (doc_id, settings.warmup_blocks),
    ).fetchall()
    for r in rows:
        enqueue_block(r["id"], priority=1)


def _insert_blocks(conn, doc_id, sec_id, blocks, lang, start_idx) -> int:
    idx = start_idx
    for text, page in blocks:
        conn.execute(
            "INSERT INTO blocks(section_id, document_id, idx, text_clean, text_hash, page)"
            " VALUES (?,?,?,?,?,?)",
            (sec_id, doc_id, idx, text, text_hash(text, settings.tts_provider, lang), page),
        )
        idx += 1
    return idx


def enqueue_block(block_id: int, priority: int = 5) -> None:
    conn = connect()
    exists = conn.execute(
        "SELECT 1 FROM jobs WHERE type='synthesize' AND status IN ('pending','running')"
        " AND json_extract(payload,'$.block_id')=?",
        (block_id,),
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO jobs(type, payload, priority) VALUES ('synthesize', ?, ?)",
            (json.dumps({"block_id": block_id}), priority),
        )


def synthesize_block(block_id: int, tts: TTSProvider) -> None:
    """Job `synthesize`: genera el MP3 de un bloque, con cache por hash."""
    conn = connect()
    b = conn.execute("SELECT * FROM blocks WHERE id=?", (block_id,)).fetchone()
    if b is None or b["audio_status"] == "done":
        return
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (b["document_id"],)).fetchone()

    # Cache global: otro bloque con el mismo hash ya sintetizado (RNF-2).
    hit = conn.execute(
        "SELECT audio_path, duration_ms FROM blocks WHERE text_hash=? AND audio_status='done' LIMIT 1",
        (b["text_hash"],),
    ).fetchone()
    if hit:
        conn.execute(
            "UPDATE blocks SET audio_path=?, duration_ms=?, audio_status='done' WHERE id=?",
            (hit["audio_path"], hit["duration_ms"], block_id),
        )
        return

    conn.execute("UPDATE blocks SET audio_status='generating' WHERE id=?", (block_id,))
    result = tts.synthesize(b["text_clean"], doc["language"])
    rel = f"audio/{b['text_hash']}.mp3"
    (settings.data_dir / rel).write_bytes(result.audio)
    cost = _track_cost(conn, b["document_id"], "tts", result.chars)
    conn.execute(
        "UPDATE blocks SET audio_path=?, duration_ms=?, audio_status='done',"
        " tts_cost_cents=? WHERE id=?",
        (rel, result.duration_ms, cost, block_id),
    )


def _track_cost(conn, doc_id: int, kind: str, chars: int) -> float:
    rate = (settings.tts_rate_cents_per_mchar if kind == "tts"
            else settings.llm_rate_cents_per_mchar)
    cost = chars * rate / 1_000_000
    conn.execute(
        "INSERT INTO costs(document_id, kind, chars, cost_cents) VALUES (?,?,?,?)",
        (doc_id, kind, chars, cost),
    )
    conn.execute(
        "UPDATE documents SET total_cost_cents = total_cost_cents + ? WHERE id=?",
        (cost, doc_id),
    )
    return cost
