"""Selección de proveedores por variable de entorno (A7-A9, RF-7.4)."""
from ..config import settings
from .base import LLMProvider, TTSProvider


def get_llm(name: str | None = None) -> LLMProvider:
    name = name or settings.llm_provider
    if name == "claude":
        from .claude_llm import ClaudeLLM
        return ClaudeLLM()
    if name == "fake":
        from .fakes import FakeLLM
        return FakeLLM()
    raise ValueError(f"LLM_PROVIDER desconocido: {name}")


def get_tts(name: str | None = None) -> TTSProvider:
    name = name or settings.tts_provider
    if name == "gemini":
        from .gemini_tts import GeminiTTS
        return GeminiTTS()
    if name == "espeak":
        from .espeak_tts import EspeakTTS
        return EspeakTTS()
    if name == "fake":
        from .fakes import FakeTTS
        return FakeTTS()
    raise ValueError(f"TTS_PROVIDER desconocido: {name}")
