"""Recuperación de contexto para el tutor (RF-4.3, RNF-3).

Sin embeddings en el MVP: la sección que se está escuchando SIEMPRE entra
(es de lo que va la pregunta el 90% de las veces), más los bloques de otras
secciones que compartan palabras clave con la pregunta (búsqueda léxica).
"""
import re

from ..db import connect

_WORD = re.compile(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ0-9]{4,}", re.UNICODE)
_STOP = {
    "este", "esta", "esto", "para", "pero", "como", "cual", "cuál", "donde", "dónde",
    "cuando", "cuándo", "sobre", "entre", "porque", "porqué", "según", "explica",
    "explícame", "dime", "significa", "that", "this", "what", "which", "where",
    "when", "does", "mean", "about", "explain", "tell",
}


def _keywords(question: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(question)} - _STOP


def build_context(
    doc_id: int, question: str, current_block_id: int | None, max_chars: int = 8000
) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT b.id, b.idx, b.text_clean, b.section_id, s.title AS section_title"
        " FROM blocks b JOIN sections s ON s.id=b.section_id"
        " WHERE b.document_id=? ORDER BY b.idx",
        (doc_id,),
    ).fetchall()
    if not rows:
        return []

    current_section = None
    if current_block_id is not None:
        for r in rows:
            if r["id"] == current_block_id:
                current_section = r["section_id"]
                break

    kws = _keywords(question)

    def score(r) -> int:
        text = r["text_clean"].lower()
        return sum(1 for k in kws if k in text)

    picked: list[dict] = []
    seen: set[int] = set()
    total = 0

    def add(r) -> bool:
        nonlocal total
        if r["id"] in seen:
            return True
        if total + len(r["text_clean"]) > max_chars:
            return False
        seen.add(r["id"])
        total += len(r["text_clean"])
        picked.append({
            "block_id": r["id"],
            "section_title": r["section_title"],
            "text": r["text_clean"],
        })
        return True

    # 1) La sección actual, entera (en orden de lectura).
    if current_section is not None:
        for r in rows:
            if r["section_id"] == current_section:
                if not add(r):
                    break

    # 2) El resto, por puntuación léxica descendente.
    rest = sorted((r for r in rows if r["id"] not in seen), key=score, reverse=True)
    for r in rest:
        if score(r) == 0:
            break
        if not add(r):
            break

    return picked
