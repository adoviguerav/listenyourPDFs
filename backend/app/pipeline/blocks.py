"""Troceo de secciones en bloques de audio (~30-90s cada uno, A3)."""
import re

TARGET = 700   # chars por bloque (≈45s a 55 chars/s)
HARD_MAX = 1100

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_into_blocks(paragraphs: list[str]) -> list[str]:
    blocks: list[str] = []
    buf = ""
    for p in paragraphs:
        candidate = (buf + " " + p).strip() if buf else p
        if len(candidate) <= TARGET:
            buf = candidate
            continue
        if buf:
            blocks.append(buf)
        if len(p) <= HARD_MAX:
            buf = p
            continue
        # Párrafo enorme: cortar por frases.
        buf = ""
        for sent in _SENTENCE_END.split(p):
            candidate = (buf + " " + sent).strip() if buf else sent
            if len(candidate) > HARD_MAX and buf:
                blocks.append(buf)
                buf = sent
            else:
                buf = candidate
    if buf:
        blocks.append(buf)
    return [b for b in blocks if b.strip()]
