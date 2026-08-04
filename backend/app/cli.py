"""CLI de la Fase 1: procesa un PDF completo sin UI.

    python -m app.cli documento.pdf [--full] [--llm fake|claude] [--tts fake|espeak|gemini]

--full sintetiza todos los bloques (no solo el arranque). Salida: estructura,
coste y carpeta con los MP3 en orden.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import db, worker
from .config import settings
from .providers import registry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--llm", default=None)
    ap.add_argument("--tts", default=None)
    ap.add_argument("--export", type=Path, help="carpeta destino para los MP3 en orden")
    args = ap.parse_args()

    db.init(settings.db_path)
    llm = registry.get_llm(args.llm)
    tts = registry.get_tts(args.tts)

    conn = db.connect()
    dest = settings.data_dir / "pdfs" / args.pdf.name
    shutil.copy(args.pdf, dest)
    doc_id = conn.execute(
        "INSERT INTO documents(title, filename) VALUES (?,?)",
        (args.pdf.stem, dest.name),
    ).lastrowid
    conn.execute(
        "INSERT INTO jobs(type, payload, priority) VALUES ('process_document', ?, 1)",
        (json.dumps({"document_id": doc_id}),),
    )
    worker.run_pending(llm=llm, tts=tts)

    if args.full:
        rows = conn.execute(
            "SELECT id FROM blocks WHERE document_id=? AND audio_status='pending' ORDER BY idx",
            (doc_id,),
        ).fetchall()
        from .pipeline.process import enqueue_block
        for r in rows:
            enqueue_block(r["id"])
        worker.run_pending(llm=llm, tts=tts)

    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    n_total = conn.execute(
        "SELECT COUNT(*) c FROM blocks WHERE document_id=?", (doc_id,)).fetchone()["c"]
    n_done = conn.execute(
        "SELECT COUNT(*) c FROM blocks WHERE document_id=? AND audio_status='done'",
        (doc_id,)).fetchone()["c"]
    print(f"doc #{doc_id} '{doc['title']}' [{doc['language']}] estado={doc['status']}")
    print(f"bloques: {n_done}/{n_total} con audio · coste: {doc['total_cost_cents']:.2f} cts")
    for s in conn.execute(
        "SELECT * FROM sections WHERE document_id=? ORDER BY idx", (doc_id,)
    ).fetchall():
        print(f"  [{s['idx']}] {s['title']}")

    if args.export:
        args.export.mkdir(parents=True, exist_ok=True)
        rows = conn.execute(
            "SELECT idx, audio_path FROM blocks WHERE document_id=? AND audio_status='done' ORDER BY idx",
            (doc_id,),
        ).fetchall()
        for r in rows:
            shutil.copy(settings.data_dir / r["audio_path"],
                        args.export / f"{r['idx']:04d}.mp3")
        print(f"exportados {len(rows)} MP3 a {args.export}")

    if doc["status"] == "error":
        print(doc["error"], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
