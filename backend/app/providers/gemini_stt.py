"""STT con Gemini (audio nativo, A7): transcripción de la pregunta del push-to-talk."""
import base64

import httpx

from ..config import settings

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = (
    "Transcribe literalmente este audio de voz. Devuelve SOLO la transcripción, "
    "sin comillas ni comentarios. Idioma probable: {lang}."
)


class GeminiSTT:
    name = "gemini"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.client = client or httpx.Client(timeout=60)

    def transcribe(self, audio: bytes, mime: str, lang_hint: str) -> str:
        r = self.client.post(
            API.format(model=settings.gemini_stt_model),
            params={"key": self.api_key},
            json={
                "contents": [{
                    "parts": [
                        {"text": PROMPT.format(lang=lang_hint)},
                        {"inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(audio).decode(),
                        }},
                    ]
                }]
            },
        )
        r.raise_for_status()
        data = r.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
