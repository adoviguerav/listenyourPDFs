"""API REST del MVP (Fase 1: sin UI; la PWA llega en Fase 2)."""
import json
import re
import secrets

from contextlib import asynccontextmanager

from fastapi import (Depends, FastAPI, HTTPException, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse, JSONResponse, Response

from .. import db
from ..config import settings
from ..pipeline.process import enqueue_block


@asynccontextmanager
async def _lifespan(app: "FastAPI"):
    db.init(settings.db_path)
    yield


app = FastAPI(title="listenyourPDFs", version="0.1.0", lifespan=_lifespan)


def auth(request: Request) -> None:
    if not settings.auth_token:
        return  # desarrollo local sin token
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip() \
        or request.query_params.get("token", "")
    if not secrets.compare_digest(supplied, settings.auth_token):
        raise HTTPException(401, "token inválido")


@app.post("/api/documents", dependencies=[Depends(auth)], status_code=202)
async def upload_document(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "se espera un PDF")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    conn = db.connect()
    doc_id = conn.execute(
        "INSERT INTO documents(title, filename) VALUES (?,?)",
        (safe.removesuffix(".pdf"), safe),
    ).lastrowid
    dest = settings.data_dir / "pdfs" / f"{doc_id}-{safe}"
    dest.write_bytes(await file.read())
    conn.execute("UPDATE documents SET filename=? WHERE id=?", (dest.name, doc_id))
    conn.execute(
        "INSERT INTO jobs(type, payload, priority) VALUES ('process_document', ?, 2)",
        (json.dumps({"document_id": doc_id}),),
    )
    return {"id": doc_id, "status": "uploaded"}


@app.get("/api/documents", dependencies=[Depends(auth)])
def list_documents():
    conn = db.connect()
    rows = conn.execute(
        """SELECT d.*,
              (SELECT COUNT(*) FROM blocks b WHERE b.document_id=d.id) AS blocks,
              (SELECT COUNT(*) FROM blocks b WHERE b.document_id=d.id AND b.audio_status='done') AS blocks_done,
              (SELECT b.idx FROM positions p JOIN blocks b ON b.id=p.block_id
                 WHERE p.document_id=d.id) AS position_idx
           FROM documents d ORDER BY d.id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/documents/{doc_id}", dependencies=[Depends(auth)])
def get_document(doc_id: int):
    conn = db.connect()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc is None:
        raise HTTPException(404, "documento no encontrado")
    sections = conn.execute(
        "SELECT * FROM sections WHERE document_id=? ORDER BY idx", (doc_id,)
    ).fetchall()
    blocks = conn.execute(
        "SELECT id, section_id, idx, audio_status, duration_ms,"
        "       substr(text_clean,1,120) AS preview"
        " FROM blocks WHERE document_id=? ORDER BY idx",
        (doc_id,),
    ).fetchall()
    return {
        **dict(doc),
        "sections": [dict(s) for s in sections],
        "playlist": [dict(b) for b in blocks],
    }


@app.get("/api/documents/{doc_id}/blocks/{block_id}/audio", dependencies=[Depends(auth)])
def block_audio(doc_id: int, block_id: int):
    conn = db.connect()
    b = conn.execute(
        "SELECT * FROM blocks WHERE id=? AND document_id=?", (block_id, doc_id)
    ).fetchone()
    if b is None:
        raise HTTPException(404, "bloque no encontrado")
    if b["audio_status"] != "done":
        enqueue_block(block_id, priority=1)  # salto a bloque frío: prioridad alta (A6)
        return JSONResponse({"status": b["audio_status"]}, status_code=202)
    return FileResponse(settings.data_dir / b["audio_path"], media_type="audio/mpeg")


@app.post("/api/documents/{doc_id}/position", dependencies=[Depends(auth)])
async def save_position(doc_id: int, request: Request):
    body = await request.json()
    conn = db.connect()
    block = conn.execute(
        "SELECT id, idx FROM blocks WHERE id=? AND document_id=?",
        (body.get("block_id"), doc_id),
    ).fetchone()
    if block is None:
        raise HTTPException(404, "bloque no encontrado")
    conn.execute(
        "INSERT INTO positions(document_id, block_id, offset_ms, updated_at)"
        " VALUES (?,?,?,datetime('now'))"
        " ON CONFLICT(document_id) DO UPDATE SET block_id=excluded.block_id,"
        " offset_ms=excluded.offset_ms, updated_at=excluded.updated_at",
        (doc_id, block["id"], int(body.get("offset_ms", 0))),
    )
    # Colchón bajo demanda (A6): sintetizar por delante de la posición.
    ahead = db.connect().execute(
        "SELECT id FROM blocks WHERE document_id=? AND idx>=? AND audio_status='pending'"
        " ORDER BY idx LIMIT ?",
        (doc_id, block["idx"], settings.warmup_blocks),
    ).fetchall()
    for r in ahead:
        enqueue_block(r["id"], priority=3)
    return {"ok": True}


@app.delete("/api/documents/{doc_id}", dependencies=[Depends(auth)])
def delete_document(doc_id: int):
    conn = db.connect()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc is None:
        raise HTTPException(404, "documento no encontrado")
    # Borrado real (RNF-4): archivos de audio no compartidos con otros docs + pdf.
    for b in conn.execute(
        "SELECT DISTINCT audio_path, text_hash FROM blocks WHERE document_id=? AND audio_path IS NOT NULL",
        (doc_id,),
    ).fetchall():
        shared = conn.execute(
            "SELECT 1 FROM blocks WHERE text_hash=? AND document_id<>? LIMIT 1",
            (b["text_hash"], doc_id),
        ).fetchone()
        if not shared:
            (settings.data_dir / b["audio_path"]).unlink(missing_ok=True)
    (settings.data_dir / "pdfs" / doc["filename"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    return {"ok": True}


@app.post("/api/documents/{doc_id}/publish-rss", dependencies=[Depends(auth)], status_code=202)
def publish_rss(doc_id: int):
    conn = db.connect()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc is None:
        raise HTTPException(404, "documento no encontrado")
    if doc["status"] != "ready":
        raise HTTPException(409, f"documento en estado {doc['status']}")
    from ..pipeline.rss import publish_document
    publish_document(doc_id)
    remaining = conn.execute(
        "SELECT COUNT(*) c FROM blocks WHERE document_id=? AND audio_status='pending'",
        (doc_id,),
    ).fetchone()["c"]
    return {"queued": True, "blocks_remaining": remaining}


@app.get("/feed.xml")
def rss_feed(request: Request):
    _check_media_token(request)
    from ..pipeline.rss import feed_xml
    xml = feed_xml(settings.public_url, settings.auth_token or "")
    return Response(content=xml, media_type="application/rss+xml")


@app.get("/audio/{doc_id}.mp3")
def full_audio(doc_id: int, request: Request):
    _check_media_token(request)
    conn = db.connect()
    doc = conn.execute("SELECT full_mp3_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc is None or not doc["full_mp3_path"]:
        raise HTTPException(404, "episodio no publicado")
    return FileResponse(settings.data_dir / doc["full_mp3_path"], media_type="audio/mpeg")


def _check_media_token(request: Request) -> None:
    """El feed y sus MP3 se autentican solo por token en query (las apps de podcast
    no mandan cabeceras)."""
    if not settings.auth_token:
        return
    if not secrets.compare_digest(request.query_params.get("token", ""), settings.auth_token):
        raise HTTPException(401, "token inválido")


@app.get("/api/qr", dependencies=[Depends(auth)])
def qr_svg():
    import segno
    q = segno.make(settings.public_url, error="m")
    return Response(content=q.svg_inline(scale=6), media_type="image/svg+xml")


@app.websocket("/ws")
async def ws_events(ws: WebSocket):
    """Eventos servidor→cliente (A4): block.ready y estado del documento suscrito.

    El worker es otro proceso; el estado compartido es SQLite, así que este
    endpoint observa la BD (~1s) y empuja los cambios por el socket.
    """
    import asyncio

    if settings.auth_token and not secrets.compare_digest(
        ws.query_params.get("token", ""), settings.auth_token
    ):
        await ws.close(code=4401)
        return
    await ws.accept()
    doc_id = int(ws.query_params.get("doc", "0"))
    known_ready: set[int] = set()
    last_status = None
    try:
        while True:
            conn = db.connect()
            doc = conn.execute(
                "SELECT status FROM documents WHERE id=?", (doc_id,)).fetchone()
            if doc and doc["status"] != last_status:
                last_status = doc["status"]
                await ws.send_json({"type": "doc.status", "document_id": doc_id,
                                    "status": last_status})
            rows = conn.execute(
                "SELECT id FROM blocks WHERE document_id=? AND audio_status='done'",
                (doc_id,)).fetchall()
            for r in rows:
                if r["id"] not in known_ready:
                    known_ready.add(r["id"])
                    await ws.send_json({"type": "block.ready", "document_id": doc_id,
                                        "block_id": r["id"]})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@app.get("/api/costs", dependencies=[Depends(auth)])
def costs():
    conn = db.connect()
    per_doc = conn.execute(
        "SELECT d.id, d.title, d.total_cost_cents FROM documents d ORDER BY d.id DESC"
    ).fetchall()
    month = conn.execute(
        "SELECT COALESCE(SUM(cost_cents),0) AS cents FROM costs"
        " WHERE created_at >= date('now','start of month')"
    ).fetchone()
    return {
        "month_cents": round(month["cents"], 2),
        "documents": [dict(r) for r in per_doc],
    }
