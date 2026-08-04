"""TTS local con espeak-ng + ffmpeg. Calidad básica; útil para desarrollo,
tests de pipeline completa y como fallback self-host sin ninguna API key."""
import subprocess
import tempfile
from pathlib import Path

from .base import AudioResult


class EspeakTTS:
    name = "espeak"

    def synthesize(self, text: str, lang: str) -> AudioResult:
        voice = "es" if lang == "es" else "en"
        with tempfile.TemporaryDirectory() as td:
            wav, mp3 = Path(td) / "b.wav", Path(td) / "b.mp3"
            subprocess.run(
                ["espeak-ng", "-v", voice, "-s", "155", "-w", str(wav)],
                input=text.encode(), check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                 "-codec:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(mp3)],
                check=True, capture_output=True,
            )
            audio = mp3.read_bytes()
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(mp3)],
                check=True, capture_output=True, text=True,
            )
            duration_ms = int(float(probe.stdout.strip() or 0) * 1000)
        return AudioResult(audio=audio, duration_ms=duration_ms, chars=len(text))
