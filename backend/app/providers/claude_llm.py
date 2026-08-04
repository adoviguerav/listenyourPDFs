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
