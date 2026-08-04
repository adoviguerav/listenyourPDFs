"""Extracción PDF → estructura (secciones + texto) con pymupdf4llm (S0.2)."""
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Para:
    text: str
    page: int  # 1-based: página del PDF donde empieza el párrafo


@dataclass
class Section:
    title: str
    paragraphs: list[Para] = field(default_factory=list)


@dataclass
class DocStructure:
    title: str
    language: str
    sections: list[Section]

    def outline(self) -> str:
        return "\n".join(f"- {s.title}" for s in self.sections)


_ES_HINTS = re.compile(
    r"\b(el|la|los|las|de|del|que|una|uno|para|con|por|este|esta|como|más|según)\b", re.I
)
_EN_HINTS = re.compile(
    r"\b(the|of|and|that|with|for|this|are|is|from|which|their|have|has)\b", re.I
)


def detect_language(text: str) -> str:
    sample = text[:4000]
    return "es" if len(_ES_HINTS.findall(sample)) > len(_EN_HINTS.findall(sample)) else "en"


def _heading(line: str) -> tuple[int, str] | None:
    m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
    if not m:
        return None
    title = m.group(2)
    title = re.sub(r"</?[a-zA-Z][^>]*>", "", title)  # HTML residual (<u>, <mark>, <sup>…)
    title = re.sub(r"\*+", "", title).strip().strip("_ ")
    return len(m.group(1)), title


def structure_from_pages(pages: list[tuple[str, int]], fallback_title: str) -> DocStructure:
    """Convierte el Markdown por página del extractor en secciones navegables,
    conservando en qué página del PDF empieza cada párrafo (para el visor).

    Solo los niveles 1-3 abren sección (los #### suelen ser ruido o subtítulos
    menores); los títulos que son puro número/página se descartan como heading.
    """
    sections: list[Section] = []
    current = Section(title="Inicio")
    doc_title = ""
    for md, page in pages:
        for rawline in md.splitlines():
            h = _heading(rawline)
            if h:
                level, title = h
                if not doc_title and level == 1 and len(title) > 3:
                    doc_title = title
                if re.fullmatch(r"[\d\s.:—-]*", title):
                    continue  # número de página u otro residuo como heading
                if level <= 3:
                    if current.paragraphs:
                        sections.append(current)
                    current = Section(title=title)
                    continue
            line = rawline.rstrip()
            if line:
                last = current.paragraphs[-1] if current.paragraphs else None
                if last and last.text and not last.text.endswith((".", ":", "!", "?")):
                    last.text = last.text + " " + line.strip()
                else:
                    current.paragraphs.append(Para(text=line.strip(), page=page))
            elif current.paragraphs and current.paragraphs[-1].text != "":
                current.paragraphs.append(Para(text="", page=page))
    if current.paragraphs:
        sections.append(current)
    for s in sections:
        s.paragraphs = [p for p in s.paragraphs if p.text]
    sections = [s for s in sections if s.paragraphs]
    full_text = " ".join(p.text for s in sections for p in s.paragraphs)
    return DocStructure(
        title=doc_title or fallback_title,
        language=detect_language(full_text),
        sections=sections,
    )


def markdown_to_structure(md: str, fallback_title: str) -> DocStructure:
    """Variante de una sola página (tests y entradas sin paginar)."""
    return structure_from_pages([(md, 1)], fallback_title)


def extract(pdf_path: Path) -> DocStructure:
    import pymupdf4llm
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    pages: list[tuple[str, int]] = []
    for i, ch in enumerate(chunks):
        meta = ch.get("metadata", {}) if isinstance(ch, dict) else {}
        page = meta.get("page", i + 1)  # pymupdf4llm: 1-based
        pages.append((ch.get("text", "") if isinstance(ch, dict) else str(ch), page))
    return structure_from_pages(pages, fallback_title=pdf_path.stem)
