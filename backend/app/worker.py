"""Worker: consume la cola de jobs persistida en SQLite (A2).

Proceso separado (`python -m app.worker`) o invocable en línea desde tests
con run_pending().
"""
import json
import time
import traceback

from . import db
from .config import settings
from .pipeline import process
from .providers import registry


def claim_next() -> dict | None:
    conn = db.connect()
    row = conn.execute(
        "SELECT * FROM jobs WHERE status='pending' ORDER BY priority, id LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    changed = conn.execute(
        "UPDATE jobs SET status='running', attempts=attempts+1,"
        " updated_at=datetime('now') WHERE id=? AND status='pending'",
        (row["id"],),
    ).rowcount
    return dict(row) if changed else None


def run_job(job: dict, llm=None, tts=None) -> None:
    payload = json.loads(job["payload"])
    llm = llm or registry.get_llm()
    tts = tts or registry.get_tts()
    if job["type"] == "process_document":
        process.process_document(payload["document_id"], llm)
    elif job["type"] == "synthesize":
        process.synthesize_block(payload["block_id"], tts)
    else:
        raise ValueError(f"tipo de job desconocido: {job['type']}")


def finish(job_id: int, error: str | None = None) -> None:
    conn = db.connect()
    conn.execute(
        "UPDATE jobs SET status=?, error=?, updated_at=datetime('now') WHERE id=?",
        ("error" if error else "done", error, job_id),
    )


def _execute(job: dict, llm, tts) -> None:
    try:
        run_job(job, llm=llm, tts=tts)
        finish(job["id"])
    except Exception:
        err = traceback.format_exc(limit=3)
        finish(job["id"], error=err)
        _mark_failed_target(job, err)


def run_pending(llm=None, tts=None, max_jobs: int = 1000, concurrency: int | None = None) -> int:
    """Ejecuta todos los jobs pendientes. Los `synthesize` corren en paralelo (A13);
    el resto en línea (pueden encolar jobs nuevos que se recogen en la siguiente vuelta)."""
    from concurrent.futures import ThreadPoolExecutor

    concurrency = concurrency or settings.tts_concurrency
    llm = llm or registry.get_llm()
    tts = tts or registry.get_tts()
    n = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while n < max_jobs:
            batch: list[dict] = []
            while len(batch) < concurrency and n + len(batch) < max_jobs:
                job = claim_next()
                if job is None:
                    break
                if job["type"] == "synthesize":
                    batch.append(job)
                else:
                    _execute(job, llm, tts)
                    n += 1
            if not batch:
                break  # cola drenada (o max_jobs alcanzado) sin sintetizables pendientes
            for f in [pool.submit(_execute, j, llm, tts) for j in batch]:
                f.result()
            n += len(batch)
    return n


def _mark_failed_target(job: dict, err: str) -> None:
    conn = db.connect()
    payload = json.loads(job["payload"])
    if job["type"] == "process_document":
        conn.execute(
            "UPDATE documents SET status='error', error=? WHERE id=?",
            (err[-500:], payload["document_id"]),
        )
    elif job["type"] == "synthesize":
        conn.execute(
            "UPDATE blocks SET audio_status='error' WHERE id=?", (payload["block_id"],)
        )


def main() -> None:
    db.init(settings.db_path)
    llm, tts = registry.get_llm(), registry.get_tts()
    print(f"worker: llm={llm.name} tts={tts.name} db={settings.db_path}")
    while True:
        if run_pending(llm=llm, tts=tts, max_jobs=10) == 0:
            time.sleep(1)


if __name__ == "__main__":
    main()
