"""Harness de evaluación del tutor (DoD Fase 3): backend/eval/exam.py.

Recibe un fichero de preguntas (JSON), las lanza contra el tutor sobre un
documento real (fixture) con FakeLLM/FakeTTS — sin red — y produce un report
JSON: por pregunta {question, answer, source, latency_first_delta_ms} y
agregados {n, with_source, refusals}.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURE = Path(__file__).parent / "fixtures" / "paper-2col.pdf"
REFUSAL = "no está en el documento"


def _ingest(settings):
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


def test_exam_runs_questions_and_writes_report(app_env, tmp_path):
    from eval.exam import run_exam

    from app.providers.fakes import FakeLLM, FakeTTS
    doc_id, conn = _ingest(app_env)
    title = conn.execute(
        "SELECT title FROM sections WHERE document_id=? AND idx=1", (doc_id,)
    ).fetchone()["title"]

    class ExamLLM(FakeLLM):
        """Responde con cita real salvo a la pregunta trampa, que rechaza (RNF-3)."""

        def answer(self, question, context, lang):
            self.calls.append("answer")
            if "unicornios" in question:
                yield "Eso no aparece en el paper.\n"
                yield f"FUENTE: {REFUSAL}"
            else:
                yield "Según el documento, la respuesta es esa.\n"
                yield f"FUENTE: {title}"

        answer_stream = answer  # el motor puede usar cualquiera de los dos nombres

    questions = [
        {"question": "¿Cuál es el objetivo del paper?", "expected_contains": "respuesta"},
        {"question": "¿Qué metodología se usa?"},
        {"question": "¿Cuántos unicornios aparecen en el estudio?"},
    ]
    qfile = tmp_path / "preguntas.json"
    qfile.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.json"

    report = run_exam(doc_id, qfile, llm=ExamLLM(), tts=FakeTTS(), out_path=out)

    # Agregados del DoD: n preguntas, cuántas con cita válida, cuántos rechazos.
    assert report["n"] == 3
    assert report["with_source"] == 2   # dos ancladas a sección existente (RF-4.3)
    assert report["refusals"] == 1      # la pregunta trampa se rechaza (RNF-3)

    assert len(report["results"]) == 3
    for r, q in zip(report["results"], questions):
        assert r["question"] == q["question"]
        assert r["answer"].strip()
        assert "source" in r
        assert r["latency_first_delta_ms"] >= 0  # L3: latencia del primer delta medida
    sources = [r["source"] for r in report["results"]]
    assert sources.count(title) == 2
    assert sources.count(REFUSAL) == 1

    # El report se persiste como JSON legible.
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8"))["n"] == 3
