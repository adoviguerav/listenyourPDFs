"""Síntesis pipelined por frases (L3, arquitectura §7): app/tutor/voice.py.

speak_stream(text_deltas, tts, lang) emite {"type":"sentence.audio","url":...,"idx":n}
por cada frase completa EN CUANTO se completa (nunca espera al texto entero), y al
final {"type":"done","first_audio_ms":X,"total_ms":Y}. Los MP3 van a
data/audio/answers/ con cache por hash, como los bloques.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _slow_tts(delay=0.1):
    from app.providers.fakes import FakeTTS

    class SlowTTS(FakeTTS):
        def synthesize(self, text, lang):
            time.sleep(delay)
            return super().synthesize(text, lang)

    return SlowTTS()


def test_first_sentence_audio_before_text_finishes(app_env):
    """(a) L3: el audio de la frase 1 llega ANTES de que el texto haya terminado."""
    from app.tutor.voice import speak_stream
    tts = _slow_tts(delay=0.1)
    state = {"text_done": False}

    def deltas():
        yield "La primera frase está completa. "
        time.sleep(0.5)  # el LLM "sigue escribiendo" la segunda
        yield "La segunda frase llega mucho después."
        state["text_done"] = True

    t0 = time.monotonic()
    first_audio_at = None
    events = []
    for ev in speak_stream(deltas(), tts, "es"):
        if ev["type"] == "sentence.audio" and first_audio_at is None:
            first_audio_at = time.monotonic() - t0
            # Pipelining real: nunca esperar todo para empezar nada.
            assert state["text_done"] is False
        events.append(ev)

    assert first_audio_at is not None
    # Frase 1 = ~0,1s de TTS; sin pipelining tardaría >=0,5s (el sleep del generador).
    assert first_audio_at < 0.45
    assert state["text_done"] is True  # al final el texto sí se consumió entero


def test_events_are_ordered_and_done_reports_latency(app_env):
    """(b)+(c) los idx van en orden y done trae first_audio_ms < total_ms (L3)."""
    from app.tutor.voice import speak_stream
    tts = _slow_tts(delay=0.1)
    # Frases largas (>25 chars) para que ninguna optimización de agrupado las una:
    # el contrato es un evento por frase completa.
    deltas = iter(["La frase número uno es suficientemente larga. ",
                   "La frase número dos también es bastante larga. ",
                   "Y la tercera frase cierra la respuesta del tutor."])
    events = list(speak_stream(deltas, tts, "es"))

    audio = [e for e in events if e["type"] == "sentence.audio"]
    assert len(audio) == 3  # un evento por frase completa
    idxs = [e["idx"] for e in audio]
    assert idxs == list(range(idxs[0], idxs[0] + len(idxs)))  # orden estricto consecutivo
    for e in audio:
        assert isinstance(e["url"], str) and e["url"]

    done = events[-1]
    assert done["type"] == "done"
    assert 0 < done["first_audio_ms"] < done["total_ms"]


def test_sentence_audio_cached_by_hash(app_env):
    """(d) los MP3 existen en disco y se cachean por hash (RNF-2): la segunda pasada
    con la misma frase no llama al TTS ni crea archivos nuevos."""
    from app.tutor.voice import speak_stream
    tts = _slow_tts(delay=0)
    answers_dir = app_env.data_dir / "audio" / "answers"
    frase = "Esta frase se sintetiza una única vez de verdad. "

    ev1 = [e for e in speak_stream(iter([frase]), tts, "es")
           if e["type"] == "sentence.audio"]
    assert ev1
    calls_after_first = len(tts.calls)
    assert calls_after_first >= 1
    files_after_first = sorted(p.name for p in answers_dir.glob("*.mp3"))
    assert files_after_first, "los MP3 de frases deben guardarse en data/audio/answers/"

    ev2 = [e for e in speak_stream(iter([frase]), tts, "es")
           if e["type"] == "sentence.audio"]
    assert ev2
    assert len(tts.calls) == calls_after_first  # sin síntesis nueva: cache por hash
    assert sorted(p.name for p in answers_dir.glob("*.mp3")) == files_after_first
    assert ev1[0]["url"] == ev2[0]["url"]  # misma frase → mismo archivo/URL


def test_short_first_sentence_does_not_stall_pipeline(app_env):
    """Regresión (hallazgo del test-writer): una primera frase corta no debe
    retener el audio hasta el final del stream (rompería L3)."""
    import time

    from app.providers.fakes import FakeTTS
    from app.tutor.voice import speak_stream

    def deltas():
        yield "Sí. "                     # frase cerrada de 3 chars
        yield "La respuesta completa llega justo después con detalle. "
        time.sleep(0.3)                  # el stream sigue vivo un rato más
        yield "Y esta es la última frase del razonamiento."

    events = []
    t0 = time.monotonic()
    first_audio_at = None
    for ev in speak_stream(deltas(), FakeTTS(), "es"):
        if ev["type"] == "sentence.audio" and first_audio_at is None:
            first_audio_at = time.monotonic() - t0
        events.append(ev)

    audios = [e for e in events if e["type"] == "sentence.audio"]
    assert audios, "no se emitió ningún audio"
    # El primer audio (con el 'Sí.' agrupado) salió ANTES del sleep del stream.
    assert first_audio_at is not None and first_audio_at < 0.3
