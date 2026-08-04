# Backend — listenyourPDFs (Fase 1)

Pipeline PDF → audio con API REST y worker. Sin UI todavía (Fase 2).

## Arrancar en local (sin API keys)

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
LLM_PROVIDER=fake TTS_PROVIDER=espeak .venv/bin/uvicorn app.api.main:app &
LLM_PROVIDER=fake TTS_PROVIDER=espeak .venv/bin/python -m app.worker &
```

Con keys reales: `ANTHROPIC_API_KEY=... GEMINI_API_KEY=...` y quitar los overrides
(`LLM_PROVIDER=claude TTS_PROVIDER=gemini` son los defectos). Requiere `espeak-ng` y
`ffmpeg` del sistema solo si se usa el TTS local.

## CLI

```bash
python -m app.cli paper.pdf --full --export ./salida   # MP3 por bloque en orden
```

## Tests

```bash
.venv/bin/pytest
```
