"""Voz de la respuesta del tutor, pipelined por frases (L3, arquitectura §7).

Regla de diseño: nunca esperar el texto completo — cada frase se sintetiza en
cuanto se cierra, mientras el LLM sigue escribiendo la siguiente. MP3 cacheados
por hash en data/audio/answers/ (repetir pregunta = voz gratis).
"""
import hashlib
import re
import time
from collections.abc import Iterable, Iterator

from ..config import settings
from ..providers.base import TTSProvider

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
MIN_CHARS = 25  # frases minúsculas se agrupan con la siguiente (menos llamadas TTS)


def _sentences(deltas: Iterable[str]) -> Iterator[str]:
    """Frases completas según llegan; las cortas se agrupan con la siguiente
    (menos llamadas TTS) pero sin retener nunca frases cerradas indefinidamente."""
    buf = ""
    for d in deltas:
        buf += d
        parts = _SENTENCE_END.split(buf)
        if len(parts) < 2:
            continue
        complete, buf = parts[:-1], parts[-1]
        acc = ""
        for s in complete:
            acc = f"{acc} {s}".strip()
            if len(acc) >= MIN_CHARS:
                yield acc
                acc = ""
        if acc:  # frase(s) corta(s) cerrada(s): se unen a lo que venga después
            buf = f"{acc} {buf}".strip()
    tail = buf.strip()
    if tail:
        yield tail


def speak_stream(
    text_deltas: Iterable[str], tts: TTSProvider, lang: str
) -> Iterator[dict]:
    t0 = time.monotonic()
    first_audio_ms: int | None = None
    out_dir = settings.data_dir / "audio" / "answers"
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, sentence in enumerate(_sentences(text_deltas)):
        # La línea FUENTE no se locuta: es metadato para pantalla/registro.
        spoken = re.sub(r"FUENTE:.*$", "", sentence, flags=re.S).strip()
        if not spoken:
            continue
        h = hashlib.sha256(f"{tts.name}:{lang}:{spoken}".encode()).hexdigest()[:32]
        path = out_dir / f"{h}.mp3"
        if not path.exists():
            result = tts.synthesize(spoken, lang)
            path.write_bytes(result.audio)
        if first_audio_ms is None:
            first_audio_ms = int((time.monotonic() - t0) * 1000)
        yield {"type": "sentence.audio", "idx": idx, "url": f"/audio/answers/{h}.mp3"}

    yield {
        "type": "done",
        "first_audio_ms": first_audio_ms if first_audio_ms is not None else 0,
        "total_ms": int((time.monotonic() - t0) * 1000),
    }
