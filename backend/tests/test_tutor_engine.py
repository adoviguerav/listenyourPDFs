"""Motor del tutor (RF-4.3, RNF-3): streaming, cita de sección y anti-alucinación.

app/tutor/engine.py: answer_stream(doc_id, question, current_block_id, llm) emite
deltas de texto; el texto completo termina SIEMPRE en una línea
"FUENTE: <sección existente>" o "FUENTE: no está en el documento".

Usa un documento sembrado directamente en BD (sin PDF) para ser rápido, y un
LLM fake local con deltas configurables (se prefiere a tocar fakes.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REFUSAL = "no está en el documento"


class StreamLLM:
    """LLM fake local: emite deltas configurables y registra cuántos se le han pedido."""
    name = "fake-stream"

    def __init__(self, deltas):
        self.deltas = list(deltas)
        self.emitted: list[str] = []  # deltas ya entregados (para medir streaming)
        self.calls: list[dict] = []

    def answer(self, question, context, lang):
        self.calls.append({"question": question, "context": context, "lang": lang})
        for d in self.deltas:
            self.emitted.append(d)
            yield d

    # El motor puede llamar al método por cualquiera de los dos nombres
    # (arquitectura §5 dice answer(); el contrato no lo fija).
    answer_stream = answer


def _seed_doc():
    """Documento mínimo directo en BD: 2 secciones con bloques (sin pipeline)."""
    from app import db
    conn = db.connect()
    doc_id = conn.execute(
        "INSERT INTO documents(title, filename, language, status)"
        " VALUES ('Doc de prueba','doc.pdf','es','ready')"
    ).lastrowid
    block_ids: list[int] = []
    for s_idx, (title, texts) in enumerate([
        ("Introducción", ["El estudio analiza la fotosíntesis en plantas."]),
        ("Métodos", ["Se usaron espectrómetros de masas.", "Las muestras se congelaron."]),
    ]):
        sec_id = conn.execute(
            "INSERT INTO sections(document_id, idx, title) VALUES (?,?,?)",
            (doc_id, s_idx, title),
        ).lastrowid
        for text in texts:
            bid = conn.execute(
                "INSERT INTO blocks(section_id, document_id, idx, text_clean, text_hash, page)"
                " VALUES (?,?,?,?,?,1)",
                (sec_id, doc_id, len(block_ids), text, f"hash{len(block_ids)}"),
            ).lastrowid
            block_ids.append(bid)
    return doc_id, block_ids, conn


def test_stream_emits_deltas_progressively(app_env):
    """(a) L3: los deltas salen según llegan, no todo de golpe al final."""
    from app.tutor import engine
    doc_id, blocks, conn = _seed_doc()
    deltas = ["La ", "fotosíntesis ", "convierte ", "luz ", "en energía.\n",
              "FUENTE: Métodos"]
    llm = StreamLLM(deltas)
    gen = engine.answer_stream(doc_id, "¿qué es la fotosíntesis?", blocks[0], llm)
    first = next(gen)
    assert isinstance(first, str) and first
    # Tras el primer delta el fake NO puede estar agotado: streaming real, no buffering.
    assert len(llm.emitted) < len(deltas)
    rest = list(gen)
    assert len([first] + rest) >= 3  # varios trozos
    full = first + "".join(rest)
    assert "fotosíntesis" in full
    assert llm.calls and llm.calls[0]["question"] == "¿qué es la fotosíntesis?"


def test_parse_source_extracts_section_line(app_env):
    """(b) RF-4.3: parse_source extrae la línea FUENTE final."""
    from app.tutor.engine import parse_source
    assert parse_source("Bla bla con contenido.\nFUENTE: Métodos") == "Métodos"
    assert parse_source(f"No lo sé.\nFUENTE: {REFUSAL}") == REFUSAL
    assert parse_source("Texto sin cita alguna.") is None


def test_refusal_is_detected(app_env):
    """(c) RNF-3: el rechazo explícito del fake se reconoce como tal."""
    from app.tutor import engine
    doc_id, blocks, conn = _seed_doc()
    llm = StreamLLM(["Esa información no aparece en el documento.\n", f"FUENTE: {REFUSAL}"])
    full = "".join(engine.answer_stream(doc_id, "¿precio del bitcoin?", blocks[0], llm))
    assert engine.parse_source(full) == REFUSAL


def test_answer_is_logged_with_source_and_cost(app_env):
    """(d) qa_log recibe la fila (question, answer, section_ref, cost_cents) y costs suma."""
    from app.tutor import engine
    doc_id, blocks, conn = _seed_doc()
    llm = StreamLLM(["Se usaron espectrómetros de masas.\n", "FUENTE: Métodos"])
    full = "".join(engine.answer_stream(doc_id, "¿qué instrumentos usaron?", blocks[0], llm))
    assert full

    row = conn.execute("SELECT * FROM qa_log").fetchone()
    assert row is not None, "answer_stream no escribió en qa_log al terminar"
    assert row["question"] == "¿qué instrumentos usaron?"
    assert "espectrómetros" in row["answer"]
    assert row["section_ref"] == "Métodos"
    assert row["cost_cents"] > 0  # RNF-2: el tutor también cuenta coste
    total = conn.execute("SELECT COALESCE(SUM(cost_cents),0) AS c FROM costs").fetchone()["c"]
    assert total > 0


def test_hallucinated_source_is_replaced_by_refusal(app_env):
    """(e) RNF-3: si la FUENTE citada no existe como sección, se sustituye por el rechazo."""
    from app.tutor import engine
    doc_id, blocks, conn = _seed_doc()
    llm = StreamLLM(["Los datos muestran un resultado claro.\n", "FUENTE: Sección Fantasma"])
    full = "".join(engine.answer_stream(doc_id, "¿qué muestran los datos?", blocks[0], llm))
    assert "Sección Fantasma" not in full  # la cita inventada nunca llega al usuario
    assert engine.parse_source(full) == REFUSAL
