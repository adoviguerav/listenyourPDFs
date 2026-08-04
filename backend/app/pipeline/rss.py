"""Feed RSS de podcast privado (RF-7.6, D16).

`publish_document` encola la síntesis restante + un job `concat_rss` que espera
a que todos los bloques estén listos, concatena a un MP3 único y publica el episodio.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from ..config import settings
from ..db import connect
from .process import enqueue_block


def publish_document(doc_id: int) -> None:
    conn = connect()
    for r in conn.execute(
        "SELECT id FROM blocks WHERE document_id=? AND audio_status='pending' ORDER BY idx",
        (doc_id,),
    ).fetchall():
        enqueue_block(r["id"], priority=4)
    exists = conn.execute(
        "SELECT 1 FROM jobs WHERE type='concat_rss' AND status IN ('pending','running')"
        " AND json_extract(payload,'$.document_id')=?",
        (doc_id,),
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO jobs(type, payload, priority) VALUES ('concat_rss', ?, 6)",
            (json.dumps({"document_id": doc_id}),),
        )


def concat_rss(doc_id: int) -> None:
    """Job `concat_rss`. Si quedan bloques sin audio, se re-encola y espera."""
    conn = connect()
    pending = conn.execute(
        "SELECT id FROM blocks WHERE document_id=? AND audio_status NOT IN ('done','error')",
        (doc_id,),
    ).fetchall()
    if pending:
        for r in pending:  # autocuración: garantizar que su síntesis está encolada
            enqueue_block(r["id"], priority=4)
        conn.execute(
            "INSERT INTO jobs(type, payload, priority) VALUES ('concat_rss', ?, 6)",
            (json.dumps({"document_id": doc_id}),),
        )
        return
    rows = conn.execute(
        "SELECT audio_path FROM blocks WHERE document_id=? AND audio_status='done' ORDER BY idx",
        (doc_id,),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"doc {doc_id}: sin bloques con audio para concatenar")
    rel = f"audio/doc-{doc_id}-full.mp3"
    out = settings.data_dir / rel
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for r in rows:
            f.write(f"file '{(settings.data_dir / r['audio_path']).resolve()}'\n")
        list_path = f.name
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", list_path, "-c", "copy", str(out)],
        check=True, capture_output=True,
    )
    Path(list_path).unlink(missing_ok=True)
    conn.execute(
        "UPDATE documents SET full_mp3_path=?, rss_published_at=datetime('now') WHERE id=?",
        (rel, doc_id),
    )


def feed_xml(base_url: str, token: str) -> str:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM documents WHERE rss_published_at IS NOT NULL ORDER BY rss_published_at DESC"
    ).fetchall()
    items = []
    for d in rows:
        url = f"{base_url}/audio/{d['id']}.mp3?token={token}"
        size = (settings.data_dir / d["full_mp3_path"]).stat().st_size \
            if d["full_mp3_path"] and (settings.data_dir / d["full_mp3_path"]).exists() else 0
        items.append(
            f"""    <item>
      <title>{escape(d['title'])}</title>
      <guid isPermaLink="false">lyp-doc-{d['id']}</guid>
      <pubDate>{d['rss_published_at']}</pubDate>
      <enclosure url="{escape(url)}" length="{size}" type="audio/mpeg"/>
    </item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>listenyourPDFs</title>
    <link>{escape(base_url)}</link>
    <description>Tus PDFs, como episodios de podcast</description>
    <language>es</language>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""
