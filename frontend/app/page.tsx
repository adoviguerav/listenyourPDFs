"use client";
// Biblioteca (RF-6.1) + subida + coste (RF-6.4) + QR (RF-7.5) + RSS (RF-7.6).
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import TokenGate from "@/components/TokenGate";
import { api, API_BASE, DocSummary, getToken, mediaUrl } from "@/lib/api";

interface Costs {
  month_cents: number;
  documents: { id: number; title: string; total_cost_cents: number }[];
}

export default function Library() {
  const [docs, setDocs] = useState<DocSummary[] | null>(null);
  const [costs, setCosts] = useState<Costs | null>(null);
  const [needToken, setNeedToken] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showQr, setShowQr] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocs(await api<DocSummary[]>("/api/documents"));
      setCosts(await api<Costs>("/api/costs"));
      setNeedToken(false);
    } catch (e) {
      if ((e as Error).message === "unauthorized") setNeedToken(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  if (needToken) return <TokenGate onDone={refresh} />;

  async function upload(file: File) {
    setUploading(true);
    const body = new FormData();
    body.append("file", file);
    try {
      await fetch(`${API_BASE}/api/documents`, {
        method: "POST",
        body,
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      });
      await refresh();
    } finally {
      setUploading(false);
    }
  }

  async function publishRss(id: number) {
    await api(`/api/documents/${id}/publish-rss`, { method: "POST" });
    refresh();
  }

  return (
    <main>
      <h1>listenyourPDFs</h1>

      <div className="card">
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          data-testid="file-input"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <button
          className="btn btn-primary btn-xl"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Subiendo…" : "➕ Subir PDF"}
        </button>
      </div>

      <div className="card">
        <h2>Biblioteca</h2>
        {docs === null && <p className="muted">Cargando…</p>}
        {docs?.length === 0 && <p className="muted">Sube tu primer PDF para escucharlo.</p>}
        {docs?.map((d) => {
          const pct = d.blocks ? Math.round((100 * (d.position_idx ?? 0)) / d.blocks) : 0;
          return (
            <Link key={d.id} href={`/doc/${d.id}`} className="doc-item card" data-testid="doc-item">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{d.title}</strong>
                <span className={`chip ${d.status === "ready" ? "ok" : d.status === "error" ? "warn" : ""}`}>
                  {d.status === "ready" ? `escuchado ${pct}%` : d.status}
                </span>
              </div>
              <div className="row muted" style={{ marginTop: "0.3rem" }}>
                <span>{d.blocks_done}/{d.blocks} bloques con audio</span>
                <span>· {(d.total_cost_cents / 100).toFixed(2)} €</span>
                {d.rss_published_at ? (
                  <span className="chip ok">en podcast</span>
                ) : (
                  d.status === "ready" && (
                    <button
                      className="btn"
                      onClick={(e) => {
                        e.preventDefault();
                        publishRss(d.id);
                      }}
                    >
                      Enviar a podcast
                    </button>
                  )
                )}
              </div>
              <div className="progress"><div style={{ width: `${pct}%` }} /></div>
            </Link>
          );
        })}
      </div>

      <div className="card">
        <h2>Coste del mes</h2>
        <p className="player-time" data-testid="month-cost">
          {costs ? (costs.month_cents / 100).toFixed(2) : "–"} €
        </p>
        <p className="muted">APIs de voz y tutor (RNF-2). Techo pactado: 20 €/mes.</p>
      </div>

      <div className="card">
        <h2>Instalar en el móvil</h2>
        <button className="btn" onClick={() => setShowQr(!showQr)}>
          {showQr ? "Ocultar QR" : "Mostrar QR"}
        </button>
        {showQr && (
          <p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mediaUrl("/api/qr")} alt="QR de la instancia" width={220} height={220} />
            <span className="muted"> Escanéalo con el móvil y “Añadir a pantalla de inicio”.</span>
          </p>
        )}
        <p className="muted">
          Podcast privado: <code>{API_BASE}/feed.xml?token=…</code> (añádelo a tu app de
          podcasts con tu token).
        </p>
      </div>
    </main>
  );
}
