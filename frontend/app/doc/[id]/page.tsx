"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import Player from "@/components/Player";
import TokenGate from "@/components/TokenGate";
import { api, DocDetail } from "@/lib/api";

export default function DocPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [needToken, setNeedToken] = useState(false);

  const load = async () => {
    try {
      setDoc(await api<DocDetail>(`/api/documents/${id}`));
      setNeedToken(false);
    } catch (e) {
      if ((e as Error).message === "unauthorized") setNeedToken(true);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (needToken) return <TokenGate onDone={load} />;
  if (!doc) return <main><p className="muted">Cargando…</p></main>;

  return (
    <main>
      <p><Link href="/">← Biblioteca</Link></p>
      <h1 data-testid="doc-title">{doc.title}</h1>
      {doc.status !== "ready" ? (
        <div className="card">
          <p className="muted">Procesando documento ({doc.status})… esta página se
            actualizará sola.</p>
          <RefreshWhileProcessing onTick={load} />
        </div>
      ) : (
        <Player doc={doc} />
      )}
    </main>
  );
}

function RefreshWhileProcessing({ onTick }: { onTick: () => void }) {
  useEffect(() => {
    const t = setInterval(onTick, 3000);
    return () => clearInterval(t);
  }, [onTick]);
  return null;
}
