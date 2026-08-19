"""Interfaces de proveedor (RF-7.4). Implementaciones seleccionadas por env var."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class CleanResult:
    text: str
    input_chars: int


@dataclass
class AudioResult:
    audio: bytes          # MP3
    duration_ms: int
    chars: int


class LLMProvider(Protocol):
    name: str

    def clean_block(self, text: str, doc_title: str, lang: str) -> CleanResult:
        """Reescribe un bloque para ser escuchado (expandir abreviaturas, quitar residuos)."""
        ...

    def intro(self, outline: str, doc_title: str, lang: str) -> str:
        """Intro de ~60s (RF-2.0) a partir del esquema del documento."""
        ...


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, lang: str) -> AudioResult: ...


class STTProvider(Protocol):
    name: str

    def transcribe(self, audio: bytes, mime: str, lang_hint: str) -> str:
        """Transcribe la pregunta hablada del usuario (push-to-talk, RF-4.1)."""
        ...
