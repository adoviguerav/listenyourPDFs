"""Golden tests de la limpieza heurística (RF-1.4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline.blocks import HARD_MAX, split_into_blocks
from app.pipeline.clean import clean_paragraph, is_table_junk

GOLDEN = [
    # (entrada extraída, salida esperada para audio)
    ("El modelo supera al estado del arte [12, 13] en ambas tareas.",
     "El modelo supera al estado del arte en ambas tareas."),
    ("**Resultados** del *experimento* con `código`",
     "Resultados del experimento con código"),
    ("Ver https://example.com/paper.pdf para más detalles.",
     "Ver enlace omitido para más detalles."),
    ("Contacto: autor@uni.edu para dudas.",
     "Contacto: correo omitido para dudas."),
    ("Andreas Gal<sup>_∗_+</sup> propuso el método.",
     "Andreas Gal propuso el método."),
    ("El   texto    con   espacios", "El texto con espacios"),
    ("[el enlace](https://x.com) explica el método.",
     "el enlace explica el método."),
]

RESIDUE = ["42", "  ", "3.", "— 17 —", "|---|---|", "| a | b |", "····"]


def test_golden_clean():
    for raw, expected in GOLDEN:
        assert clean_paragraph(raw) == expected, raw


def test_residue_removed():
    for raw in RESIDUE:
        if raw.strip().startswith("|"):
            assert is_table_junk(raw), raw
        else:
            assert clean_paragraph(raw) == "", raw


def test_blocks_respect_max_and_keep_content():
    paras = ["Frase corta uno.", "Frase corta dos.",
             ("Una frase larga que se repite mucho. " * 60).strip()]
    blocks = split_into_blocks(paras)
    assert all(len(b) <= HARD_MAX + 50 for b in blocks)
    total = " ".join(blocks)
    assert "Frase corta uno." in total and "Frase corta dos." in total
    assert total.count("Una frase larga") == 60


def test_heading_titles_strip_html():
    from app.pipeline.extract import markdown_to_structure
    md = "# **Doc principal**\n\ntexto uno.\n\n## Date: <u>12/01/2015</u>\n\ntexto dos.\n\n## <mark>SECCIÓN X</mark>\n\ntexto tres."
    s = markdown_to_structure(md, "f")
    titles = [sec.title for sec in s.sections]
    assert "Date: 12/01/2015" in titles
    assert "SECCIÓN X" in titles
    assert not any("<" in t for t in titles)
