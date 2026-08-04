"use client";
// Reproductor (RF-3.1/3.3/3.4-M): playlist de bloques encadenados sin cortes,
// Media Session para lock screen, posición persistida cada 5s, WS para block.ready.
// RNF-8/S0.1: la reanudación tras background se trata como NO fiable — al volver a
// foreground se rearma el <audio> y la Media Session desde el estado guardado.
import { useCallback, useEffect, useRef, useState } from "react";
import PdfViewer from "@/components/PdfViewer";
import { api, Block, DocDetail, mediaUrl, wsUrl } from "@/lib/api";

const fmt = (ms: number) => {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export default function Player({ doc: initial }: { doc: DocDetail }) {
  const [doc, setDoc] = useState(initial);
  const startIdx = initial.position
    ? initial.playlist.findIndex((b) => b.id === initial.position!.block_id)
    : 0;
  const [idx, setIdx] = useState(Math.max(0, startIdx));
  const [playing, setPlaying] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [rate, setRate] = useState(1);
  const [elapsed, setElapsed] = useState(initial.position?.offset_ms ?? 0);
  const audioRef = useRef<HTMLAudioElement>(null);
  const idxRef = useRef(idx);
  idxRef.current = idx;
  const docRef = useRef(doc);
  docRef.current = doc;

  const block: Block | undefined = doc.playlist[idx];
  const section = doc.sections.find((s) => s.id === block?.section_id);

  // Visor PDF-primero: la página sigue al audio salvo que el usuario navegue a mano.
  const [viewPage, setViewPage] = useState(doc.playlist[Math.max(0, startIdx)]?.page ?? 1);
  const [numPages, setNumPages] = useState(0);
  const [follow, setFollow] = useState(true);
  const [showText, setShowText] = useState(false);

  useEffect(() => {
    if (follow && block?.page) setViewPage(block.page);
  }, [follow, block?.page]);

  const goPage = (delta: number) => {
    setFollow(false);
    setViewPage((p) => Math.min(Math.max(1, p + delta), numPages || p + delta));
  };

  const readFromPage = () => {
    const d = docRef.current;
    const i = d.playlist.findIndex((b) => b.page >= viewPage);
    setFollow(true);
    if (i >= 0) play(i);
  };

  const savePosition = useCallback(async () => {
    const a = audioRef.current;
    const b = docRef.current.playlist[idxRef.current];
    if (!a || !b) return;
    try {
      await api(`/api/documents/${docRef.current.id}/position`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ block_id: b.id, offset_ms: Math.floor(a.currentTime * 1000) }),
      });
    } catch {}
  }, []);

  // Posición al servidor cada 5s mientras suena (RNF-5).
  useEffect(() => {
    const t = setInterval(() => { if (playing) savePosition(); }, 5000);
    return () => clearInterval(t);
  }, [playing, savePosition]);

  // WS: refrescar bloques según se generan (A4).
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(wsUrl(doc.id));
      ws.onmessage = async (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "block.ready" || msg.type === "doc.status") {
          const fresh = await api<DocDetail>(`/api/documents/${doc.id}`);
          setDoc((d) => ({ ...fresh, position: d.position }));
        }
      };
      ws.onclose = () => { if (!closed) setTimeout(connect, 2000); };
    };
    connect();
    return () => { closed = true; ws?.close(); };
  }, [doc.id]);

  const play = useCallback(async (targetIdx?: number, offsetMs = 0) => {
    const a = audioRef.current;
    const d = docRef.current;
    const i = targetIdx ?? idxRef.current;
    const b = d.playlist[i];
    if (!a || !b) return;
    if (b.audio_status !== "done") {
      setWaiting(true);
      await fetch(mediaUrl(`/api/documents/${d.id}/blocks/${b.id}/audio`));
      const poll = setInterval(async () => {
        const fresh = await api<DocDetail>(`/api/documents/${d.id}`);
        setDoc((prev) => ({ ...fresh, position: prev.position }));
        if (fresh.playlist[i]?.audio_status === "done") {
          clearInterval(poll);
          setWaiting(false);
          play(i, offsetMs);
        }
      }, 2000);
      return;
    }
    setIdx(i);
    a.src = mediaUrl(`/api/documents/${d.id}/blocks/${b.id}/audio`);
    a.currentTime = offsetMs / 1000;
    a.playbackRate = rate;
    await a.play();
  }, [rate]);

  const next = useCallback(() => {
    if (idxRef.current + 1 < docRef.current.playlist.length) play(idxRef.current + 1);
    else setPlaying(false);
  }, [play]);

  const seek = useCallback((deltaS: number) => {
    const a = audioRef.current;
    if (!a || !a.duration) return;
    const t = a.currentTime + deltaS;
    if (t < 0 && idxRef.current > 0) play(idxRef.current - 1);
    else if (t > a.duration) next();
    else a.currentTime = Math.max(0, t);
  }, [next, play]);

  // Media Session (RF-3.3): controles del sistema / pantalla de bloqueo.
  useEffect(() => {
    if (!("mediaSession" in navigator) || !block) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: doc.title,
      artist: section?.title ?? "listenyourPDFs",
      album: "listenyourPDFs",
    });
    const ms = navigator.mediaSession;
    ms.setActionHandler("play", () => audioRef.current?.play());
    ms.setActionHandler("pause", () => audioRef.current?.pause());
    ms.setActionHandler("seekbackward", () => seek(-15));
    ms.setActionHandler("seekforward", () => seek(15));
    ms.setActionHandler("nexttrack", next);
  }, [doc.title, section?.title, block, seek, next]);

  // Rearme tras volver de background (veredicto S0.1): estado desde refs.
  useEffect(() => {
    const onVisible = () => {
      const a = audioRef.current;
      if (document.visibilityState === "visible" && a && playing && a.paused && !a.ended) {
        a.play().catch(() => setPlaying(false));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [playing]);

  const pct = doc.playlist.length ? Math.round((100 * idx) / doc.playlist.length) : 0;

  return (
    <div>
      <div className="card">
        <PdfViewer
          url={mediaUrl(`/api/documents/${doc.id}/pdf`)}
          page={viewPage}
          onNumPages={setNumPages}
        />
        <div className="row" style={{ justifyContent: "space-between", marginTop: "0.6rem" }}>
          <button className="btn" onClick={() => goPage(-1)} aria-label="página anterior">‹</button>
          <span className="chip" data-testid="page-pos">
            pág. {viewPage}{numPages ? ` / ${numPages}` : ""}
          </span>
          <button className="btn" onClick={() => goPage(1)} aria-label="página siguiente" data-testid="next-page">›</button>
        </div>
        {(!follow || !playing) && (
          <button
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "0.6rem" }}
            data-testid="read-from-page"
            onClick={readFromPage}
          >
            🔊 Leer desde esta página
          </button>
        )}
      </div>

      <div className="card">
        <p className="muted">{section?.title}</p>
        <button className="btn" onClick={() => setShowText(!showText)}>
          {showText ? "Ocultar texto" : "Ver texto del bloque"}
        </button>
        {showText && (
          <p className="block-text" data-testid="block-text">{block?.preview}…</p>
        )}
        <div className="row" style={{ justifyContent: "space-between", marginTop: "0.6rem" }}>
          <span className="player-time" data-testid="elapsed">{fmt(elapsed)}</span>
          <span className="chip" data-testid="block-pos">bloque {idx + 1}/{doc.playlist.length}</span>
        </div>
        <div className="progress"><div style={{ width: `${pct}%` }} /></div>
      </div>

      <div className="card">
        <button
          className="btn btn-primary btn-xl"
          data-testid="play-button"
          onClick={() => {
            const a = audioRef.current;
            if (playing) a?.pause();
            else if (a?.src && !a.ended) a.play();
            else play(idx, doc.position?.block_id === block?.id ? doc.position.offset_ms : 0);
          }}
        >
          {waiting ? "Generando audio…" : playing ? "⏸ Pausar" : "▶ Reproducir"}
        </button>
        <div className="row" style={{ marginTop: "0.7rem" }}>
          <button className="btn" onClick={() => seek(-15)}>−15s</button>
          <button className="btn" onClick={() => seek(15)}>+15s</button>
          <button className="btn" data-testid="rate-button" onClick={() => {
            const r = rate >= 3 ? 0.75 : Math.round((rate + 0.25) * 100) / 100;
            setRate(r);
            if (audioRef.current) audioRef.current.playbackRate = r;
          }}>
            {rate.toFixed(2)}x
          </button>
          <button className="btn" onClick={next}>Siguiente ▸</button>
        </div>
      </div>

      <audio
        ref={audioRef}
        data-testid="audio"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { savePosition(); next(); }}
        onTimeUpdate={(e) => setElapsed(e.currentTarget.currentTime * 1000)}
      />
    </div>
  );
}
