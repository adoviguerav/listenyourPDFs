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

    def clean_block(self, text: str, doc_title: str, lang: str) -> CleanResult:
        self.calls.append("clean")
        return CleanResult(text=text.strip(), input_chars=len(text))

    def intro(self, outline: str, doc_title: str, lang: str) -> str:
        self.calls.append("intro")
        return f"Vas a escuchar {doc_title}. Esquema: {outline[:200]}"


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
