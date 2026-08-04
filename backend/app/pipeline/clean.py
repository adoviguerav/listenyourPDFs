"""Limpieza heurística para audio (RF-1.4), determinista y testeable con golden files.

Esta capa quita lo que NUNCA debe llegar al TTS. El pulido fino (abreviaturas,
símbolos, residuos sutiles) lo hace después el LLM (providers.LLMProvider.clean_block);
si el LLM no está disponible, esta salida ya es escuchable.
"""
import re

_MD_EMPHASIS = re.compile(r"(\*\*|\*|__|`)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_EMAIL = re.compile(r"\S+@\S+\.\S+")
_CITE_BRACKET = re.compile(r"\s*\[[\d,\s;–-]+\]")
_SUP_MARKER = re.compile(r"<sup>.*?</sup>|<sub>.*?</sub>", re.S)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_PAGE_NUMBER_LINE = re.compile(r"^[\s\d.:–—-]{1,10}$")
_FIG_TABLE_LINE = re.compile(r"^(figure|fig\.|table|tabla|figura)\s*\d+[.:]", re.I)
_MULTISPACE = re.compile(r"[ \t]{2,}")


def clean_paragraph(text: str) -> str:
    """Limpia un párrafo extraído. Devuelve '' si el párrafo entero es residuo."""
    t = text.strip()
    if not t or _PAGE_NUMBER_LINE.fullmatch(t):
        return ""
    t = _SUP_MARKER.sub("", t)
    t = _HTML_TAG.sub("", t)
    t = _MD_LINK.sub(r"\1", t)
    t = _MD_EMPHASIS.sub("", t)
    t = _CITE_BRACKET.sub("", t)
    t = _URL.sub("enlace omitido", t)
    t = _EMAIL.sub("correo omitido", t)
    t = _MULTISPACE.sub(" ", t)
    t = t.strip()
    # Párrafos que quedan sin contenido alfabético real (restos de tablas, reglas, etc.)
    if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", t)) < 3:
        return ""
    return t


def is_table_junk(text: str) -> bool:
    """Filas de tabla Markdown: en MVP no se narran (RF-1.5 llega en v1)."""
    t = text.strip()
    return t.startswith("|") or bool(re.fullmatch(r"[|\s:-]+", t))
