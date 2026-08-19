#!/usr/bin/env python3
"""Examen del tutor (DoD Fase 3): lanza N preguntas contra un documento y produce
un report JSON con respuesta, fuente citada, latencia del primer delta y agregados.

Con fakes (CI, sin red):
    LYP_DATA_DIR=... python -m eval.exam --doc 1 --questions eval/preguntas.json \
        --llm fake --out report.json
Con APIs reales (el autor; el criterio ≥18/20 con cita y 0 inventadas se corrige a mano
leyendo el report):
    ANTHROPIC_API_KEY=... python -m eval.exam --doc 1 --questions eval/preguntas.json
"""
import argparse
import json
import time
from pathlib import Path

from app import db
from app.config import settings
from app.providers import registry
from app.tutor.engine import NO_SOURCE, answer_stream, parse_source


def run_exam(doc_id: int, questions_path: Path, llm, tts=None,
             out_path: Path | None = None) -> dict:
    questions = json.loads(Path(questions_path).read_text(encoding="utf-8"))
    results = []
    for q in questions:
        t0 = time.monotonic()
        first_delta_ms = None
        parts: list[str] = []
        deltas_iter = answer_stream(doc_id, q["question"], q.get("block_id"), llm)

        def _tee():
            nonlocal first_delta_ms
            for delta in deltas_iter:
                if first_delta_ms is None:
                    first_delta_ms = int((time.monotonic() - t0) * 1000)
                parts.append(delta)
                yield delta

        first_audio_ms = None
        if tts is not None:
            from app.tutor.voice import speak_stream
            for ev in speak_stream(_tee(), tts, "es"):
                if ev["type"] == "done":
                    first_audio_ms = ev["first_audio_ms"]
        else:
            for _ in _tee():
                pass
        answer = "".join(parts)
        source = parse_source(answer)
        results.append({
            "question": q["question"],
            "answer": answer,
            "source": source,
            "refused": source == NO_SOURCE,
            "latency_first_delta_ms": first_delta_ms or 0,
            "latency_first_audio_ms": first_audio_ms,
            "expected_contains": q.get("expected_contains"),
            "contains_expected": (
                q["expected_contains"].lower() in answer.lower()
                if q.get("expected_contains") else None
            ),
        })
    lat = sorted(r["latency_first_delta_ms"] for r in results)
    report = {
        "doc_id": doc_id,
        "n": len(results),
        "with_source": sum(1 for r in results if r["source"] and not r["refused"]),
        "refusals": sum(1 for r in results if r["refused"]),
        "latency_p50_ms": lat[len(lat) // 2] if lat else 0,
        "latency_max_ms": lat[-1] if lat else 0,
        "results": results,
    }
    if out_path is not None:
        Path(out_path).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", type=int, required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--llm", default=None)
    ap.add_argument("--out", type=Path, default=Path("exam-report.json"))
    args = ap.parse_args()

    db.init(settings.db_path)
    llm = registry.get_llm(args.llm)
    report = run_exam(args.doc, args.questions, llm,
                      tts=registry.get_tts(), out_path=args.out)
    print(f"{report['n']} preguntas · {report['with_source']} con fuente · "
          f"{report['refusals']} rechazos · p50 primer delta {report['latency_p50_ms']}ms")
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
