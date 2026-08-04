"""TTS Gemini (Google AI API). Devuelve PCM 24kHz s16le; se convierte a MP3 con ffmpeg."""
import base64
import subprocess
import tempfile
from pathlib import Path

import httpx

from ..config import settings
from .base import AudioResult

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiTTS:
    name = "gemini"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.client = client or httpx.Client(timeout=300)

    def synthesize(self, text: str, lang: str) -> AudioResult:
        r = self.client.post(
            API.format(model=settings.gemini_tts_model),
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": settings.gemini_tts_voice}
                        }
                    },
                },
            },
        )
        r.raise_for_status()
        data = r.json()
        b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        pcm = base64.b64decode(b64)
        return self._pcm_to_mp3(pcm, len(text))

    @staticmethod
    def _pcm_to_mp3(pcm: bytes, chars: int) -> AudioResult:
        with tempfile.TemporaryDirectory() as td:
            raw, mp3 = Path(td) / "b.pcm", Path(td) / "b.mp3"
            raw.write_bytes(pcm)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000",
                 "-ac", "1", "-i", str(raw), "-codec:a", "libmp3lame", "-b:a", "64k",
                 str(mp3)],
                check=True, capture_output=True,
            )
            audio = mp3.read_bytes()
        duration_ms = int(len(pcm) / (24000 * 2) * 1000)  # s16le mono
        return AudioResult(audio=audio, duration_ms=duration_ms, chars=chars)
