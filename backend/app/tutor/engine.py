"""Motor del tutor (RF-4.3, RNF-3): respuesta en streaming anclada al documento.

Contrato de salida: el texto completo termina SIEMPRE con una línea
"FUENTE: <título de sección>" o "FUENTE: no está en el documento".
Si el LLM cita una sección que no existe en el documento, la cita se
sustituye por "no está en el documento" (anti-alucinación de cita) — para
eso la posible línea FUENTE se retiene y solo se emite ya validada.
"""
import re
from collections.abc import Iterator

from ..db import connect
from .retrieval import build_context

NO_SOURCE = "no está en el documento"
_SOURCE_LINE = re.compile(r"^FUENTE:\s*(.+?)\s*$", re.MULTILINE)


def parse_source(text: str) -> str | None:
    matches = _SOURCE_LINE.findall(text)
    return matches[-1] if matches else None


def _could_be_source_tail(tail: str) -> bool:
    """¿El final del texto podría ser una línea FUENTE aún incompleta?"""
    line = tail.rsplit("\n", 1)[-1]
    return line != "" and ("FUENTE:".startswith(line[:7]) or line.startswith("FUENTE"))


def answer_stream(
    doc_id: int, question: str, current_block_id: int | None, llm
) -> Iterator[str]:
    conn = connect()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc is None:
        raise ValueError(f"documento {doc_id} no existe")
    context = build_context(doc_id, question, current_block_id)
    titles = {r["title"] for r in conn.execute(
        "SELECT title FROM sections WHERE document_id=?", (doc_id,)).fetchall()}

    full = ""
    held = ""  # cola retenida: posible línea FUENTE en construcción
    for delta in llm.answer_stream(question, context, doc["language"]):
        held += delta
        if _could_be_source_tail(held):
            # Emitir todo lo anterior a la última línea; retener la posible FUENTE.
            if "\n" in held:
                emit, held = held.rsplit("\n", 1)
                emit += "\n"
                full += emit
                yield emit
            continue
        full += held
        yield held
        held = ""

    # Validar la cola retenida (la línea FUENTE, si lo era).
    source = parse_source(held) or parse_source(full)
    if source is None:
        tail = held + ("\n" if held and not held.endswith("\n") else "") + f"FUENTE: {NO_SOURCE}"
        source = NO_SOURCE
    elif source != NO_SOURCE and source not in titles:
        tail = _SOURCE_LINE.sub(f"FUENTE: {NO_SOURCE}", held) if held else f"\nFUENTE: {NO_SOURCE}"
        source = NO_SOURCE
    else:
        tail = held
    if tail:
        full += tail
        yield tail

    from ..pipeline.process import _track_cost
    cost = _track_cost(conn, doc_id, "llm", len(full) + sum(len(c["text"]) for c in context))
    conn.execute(
        "INSERT INTO qa_log(document_id, block_id, question, answer, section_ref, cost_cents)"
        " VALUES (?,?,?,?,?,?)",
        (doc_id, current_block_id, question, full, source, cost),
    )
