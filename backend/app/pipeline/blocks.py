"""Troceo de secciones en bloques de audio (~30-90s cada uno, A3).

Cada bloque conserva la página del PDF donde empieza (visor sincronizado a nivel
de página): entrada [(texto, página)], salida [(bloque, página)].
"""
import re

TARGET = 700   # chars por bloque (≈45s a 55 chars/s)
HARD_MAX = 1100

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_into_blocks(paragraphs: list[tuple[str, int]]) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    buf, buf_page = "", 1
    for p, page in paragraphs:
        candidate = (buf + " " + p).strip() if buf else p
        if len(candidate) <= TARGET:
            if not buf:
                buf_page = page
            buf = candidate
            continue
        if buf:
            blocks.append((buf, buf_page))
        if len(p) <= HARD_MAX:
            buf, buf_page = p, page
            continue
        # Párrafo enorme: cortar por frases.
        buf, buf_page = "", page
        for sent in _SENTENCE_END.split(p):
            candidate = (buf + " " + sent).strip() if buf else sent
            if len(candidate) > HARD_MAX and buf:
                blocks.append((buf, buf_page))
                buf = sent
            else:
                buf = candidate
    if buf:
        blocks.append((buf, buf_page))
    return [(b, pg) for b, pg in blocks if b.strip()]
