"""LLM Claude (Anthropic API) para limpieza e intro. HTTP directo con httpx."""
import httpx

from ..config import settings
from .base import CleanResult

API = "https://api.anthropic.com/v1/messages"

CLEAN_SYSTEM = (
    "Eres el preparador de audio de un lector de PDFs. Reescribes bloques de texto "
    "extraídos de un PDF para que un TTS los narre. Reglas estrictas: conserva TODO el "
    "contenido y el idioma original; elimina residuos de extracción (números de página "
    "sueltos, cabeceras repetidas, marcadores de cita como [12] o (Smith, 2020) salvo que "
    "sean parte de la frase); expande abreviaturas y símbolos a palabras (Fig. 2 → "
    "'la figura 2', % → 'por ciento', e.g. → 'por ejemplo'); convierte URLs en 'enlace "
    "omitido'. NO resumas, NO añadas contenido, NO comentes. Devuelve solo el texto listo."
)

INTRO_SYSTEM = (
    "Eres un tutor que prepara al oyente antes de escuchar un documento entero en audio. "
    "A partir del título y el esquema de secciones, escribe una intro de unos 60 segundos "
    "(140-170 palabras) en el idioma del documento: qué es, cuál parece ser la idea "
    "central, cómo está organizado y en qué merece la pena fijarse. Tono directo, sin "
    "florituras, sin inventar contenido que el esquema no soporte. Devuelve solo la intro."
)


TUTOR_SYSTEM = (
    "Eres el tutor de audio de un lector de PDFs. El usuario está ESCUCHANDO un documento "
    "y te hace una pregunta por voz. Reglas estrictas:\n"
    "1. Responde SOLO con información de los extractos del documento que se te dan. "
    "Si la respuesta no está en ellos, dilo claramente y no inventes nada.\n"
    "2. Responde en el idioma de la pregunta, en tono de profesor cercano, y BREVE "
    "(esto se convierte en voz: 3-6 frases salvo que pidan más).\n"
    "3. Tu última línea debe ser EXACTAMENTE 'FUENTE: <título de la sección usada>' "
    "copiando el título literal de un extracto, o 'FUENTE: no está en el documento' "
    "si no pudiste responder desde los extractos.\n"
    "4. No uses markdown ni listas: prosa hablada."
)


class ClaudeLLM:
    name = "claude"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.client = client or httpx.Client(timeout=120)

    def _call(self, system: str, user: str, model: str, max_tokens: int) -> str:
        r = self.client.post(
            API,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        r.raise_for_status()
        return "".join(
            part["text"] for part in r.json()["content"] if part["type"] == "text"
        ).strip()

    def clean_block(self, text: str, doc_title: str, lang: str) -> CleanResult:
        out = self._call(
            CLEAN_SYSTEM,
            f"Documento: {doc_title}\nIdioma: {lang}\n\nBloque:\n{text}",
            settings.claude_model_clean,
            max_tokens=2048,
        )
        return CleanResult(text=out, input_chars=len(text))

    def intro(self, outline: str, doc_title: str, lang: str) -> str:
        return self._call(
            INTRO_SYSTEM,
            f"Título: {doc_title}\nIdioma: {lang}\nEsquema:\n{outline}",
            settings.claude_model_tutor,
            max_tokens=1024,
        )

    def answer_stream(self, question: str, context: list[dict], lang: str):
        """Deltas de texto en streaming (SSE de la API de Anthropic)."""
        import json as _json

        excerpts = "\n\n".join(
            f"[Sección: {c['section_title']}]\n{c['text']}" for c in context
        ) or "(sin extractos: el documento no aportó contexto)"
        with self.client.stream(
            "POST",
            API,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.claude_model_tutor,
                "max_tokens": 1024,
                "stream": True,
                "system": TUTOR_SYSTEM,
                "messages": [{
                    "role": "user",
                    "content": f"Extractos del documento:\n\n{excerpts}\n\n"
                               f"Pregunta del oyente: {question}",
                }],
            },
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = _json.loads(line[6:])
                except ValueError:
                    continue
                if ev.get("type") == "content_block_delta":
                    text = ev.get("delta", {}).get("text", "")
                    if text:
                        yield text
