#!/usr/bin/env python3
"""Spike S0.2 — compara extractores de PDF para la pipeline de listenyourPDFs.

Para cada PDF del corpus y cada extractor mide lo que importa para AUDIO:
tiempo, texto total, detección de estructura (headings), y muestras del
arranque/medio del texto para juzgar orden de lectura y basura residual.
"""
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).parent
PDFS = sorted((HERE / "pdfs").glob("*.pdf"))
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def run_pymupdf4llm(pdf: Path) -> dict:
    import pymupdf4llm
    md = pymupdf4llm.to_markdown(str(pdf))
    return {"markdown": md}


def run_docling(pdf: Path) -> dict:
    from docling.document_converter import DocumentConverter
    global _docling_conv
    if "_docling_conv" not in globals():
        _docling_conv = DocumentConverter()
    result = _docling_conv.convert(str(pdf))
    return {"markdown": result.document.export_to_markdown()}


EXTRACTORS = {"pymupdf4llm": run_pymupdf4llm, "docling": run_docling}


def analyze(md: str) -> dict:
    lines = md.splitlines()
    headings = [l for l in lines if l.strip().startswith("#")]
    tables = sum(1 for l in lines if l.strip().startswith("|"))
    return {
        "chars": len(md),
        "lines": len(lines),
        "headings": len(headings),
        "heading_sample": headings[:12],
        "table_lines": tables,
        "start_sample": md[:600],
        "middle_sample": md[len(md) // 2 : len(md) // 2 + 600],
    }


def main():
    only = sys.argv[1:] or list(EXTRACTORS)
    report = {}
    for pdf in PDFS:
        report[pdf.name] = {}
        for name in only:
            fn = EXTRACTORS[name]
            t0 = time.time()
            try:
                res = fn(pdf)
                dt = round(time.time() - t0, 1)
                a = analyze(res["markdown"])
                a["seconds"] = dt
                report[pdf.name][name] = a
                (OUT / f"{pdf.stem}--{name}.md").write_text(res["markdown"])
                print(f"OK  {pdf.name:24s} {name:12s} {dt:6.1f}s "
                      f"{a['chars']:8d} chars  {a['headings']:3d} headings")
            except Exception as e:
                report[pdf.name][name] = {"error": f"{type(e).__name__}: {e}"}
                print(f"ERR {pdf.name:24s} {name:12s} {type(e).__name__}: {e}")
                traceback.print_exc(limit=1)
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nInforme: {OUT/'report.json'}")


if __name__ == "__main__":
    main()
