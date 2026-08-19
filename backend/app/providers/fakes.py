"""Proveedores deterministas para tests y desarrollo sin API keys."""
from .base import AudioResult, CleanResult

# MP3 mínimo válido: un frame de silencio (MPEG-1 Layer III 44.1kHz mono).
SILENT_MP3_FRAME = bytes.fromhex(
    "fffb90640000" + "00" * 412
)


class FakeLLM:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []
        # Respuesta del tutor configurable; None → respuesta genérica con FUENTE
        # de la primera sección del contexto (contrato del engine).
        self.answer_deltas: list[str] | None = None

    def clean_block(self, text: str, doc_title: str, lang: str) -> CleanResult:
        self.calls.append("clean")
        return CleanResult(text=text.strip(), input_chars=len(text))

    def intro(self, outline: str, doc_title: str, lang: str) -> str:
        self.calls.append("intro")
        return f"Vas a escuchar {doc_title}. Esquema: {outline[:200]}"

    def answer_stream(self, question: str, context: list[dict], lang: str):
        self.calls.append("answer")
        if self.answer_deltas is not None:
            yield from self.answer_deltas
            return
        section = context[0]["section_title"] if context else "ninguna"
        text = (f"Según el documento, sobre tu pregunta «{question[:60]}» puedo decirte "
                f"que el contenido relevante está tratado con detalle. Esta es una "
                f"respuesta simulada del tutor para desarrollo y tests. "
                f"\nFUENTE: {section}")
        for i in range(0, len(text), 24):
            yield text[i:i + 24]


class FakeSTT:
    name = "fake"

    def __init__(self, text: str = "¿Qué significa esto que estoy escuchando?"):
        self.transcript = text
        self.calls: list[tuple[int, str, str]] = []  # (bytes, mime, lang_hint)

    def transcribe(self, audio: bytes, mime: str, lang_hint: str) -> str:
        self.calls.append((len(audio), mime, lang_hint))
        return self.transcript


class FakeTTS:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, text: str, lang: str) -> AudioResult:
        self.calls.append(text[:40])
        # ~55 chars/seg de narración: duración proporcional y determinista.
        return AudioResult(
            audio=SILENT_MP3_FRAME,
            duration_ms=int(len(text) / 55 * 1000),
            chars=len(text),
        )
