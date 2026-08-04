"use client";
// Visor del PDF original (vista por defecto del documento): renderiza la página
// actual con pdf.js a ancho completo. El paso de páginas lo controla el padre.
import { useEffect, useRef, useState } from "react";

type PdfDoc = {
  numPages: number;
  getPage: (n: number) => Promise<{
    getViewport: (o: { scale: number }) => { width: number; height: number; scale: number };
    render: (o: { canvasContext: CanvasRenderingContext2D; viewport: unknown }) => { promise: Promise<void> };
  }>;
};

export default function PdfViewer({
  url,
  page,
  onNumPages,
}: {
  url: string;
  page: number;
  onNumPages: (n: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [doc, setDoc] = useState<PdfDoc | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        const d = (await pdfjs.getDocument({ url }).promise) as unknown as PdfDoc;
        if (cancelled) return;
        setDoc(d);
        onNumPages(d.numPages);
      } catch {
        if (!cancelled) setError("No se pudo cargar el PDF");
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  useEffect(() => {
    if (!doc || !canvasRef.current || !wrapRef.current) return;
    let cancelled = false;
    (async () => {
      const p = await doc.getPage(Math.min(Math.max(1, page), doc.numPages));
      if (cancelled) return;
      const canvas = canvasRef.current!;
      const width = wrapRef.current!.clientWidth;
      const base = p.getViewport({ scale: 1 });
      const dpr = window.devicePixelRatio || 1;
      const scale = (width / base.width) * dpr;
      const viewport = p.getViewport({ scale });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / dpr}px`;
      canvas.style.height = `${viewport.height / dpr}px`;
      const ctx = canvas.getContext("2d")!;
      await p.render({ canvasContext: ctx, viewport }).promise;
    })();
    return () => { cancelled = true; };
  }, [doc, page]);

  if (error) return <p className="muted">{error}</p>;
  return (
    <div ref={wrapRef} style={{ overflow: "hidden", borderRadius: 8 }}>
      <canvas data-testid="pdf-canvas" ref={canvasRef} style={{ display: "block", maxWidth: "100%" }} />
    </div>
  );
}
