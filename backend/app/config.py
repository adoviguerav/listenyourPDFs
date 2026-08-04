"""Configuración por variables de entorno (BYOK, RF-7.2)."""
import os
from pathlib import Path


def _data_dir() -> Path:
    d = Path(os.environ.get("LYP_DATA_DIR", "./data")).resolve()
    (d / "pdfs").mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(parents=True, exist_ok=True)
    return d


class Settings:
    def __init__(self) -> None:
        self.data_dir = _data_dir()
        self.db_path = self.data_dir / "db.sqlite"
        self.auth_token = os.environ.get("LYP_TOKEN", "")

        self.llm_provider = os.environ.get("LLM_PROVIDER", "claude")
        self.tts_provider = os.environ.get("TTS_PROVIDER", "gemini")

        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

        self.claude_model_clean = os.environ.get("CLAUDE_MODEL_CLEAN", "claude-haiku-4-5-20251001")
        self.claude_model_tutor = os.environ.get("CLAUDE_MODEL_TUTOR", "claude-sonnet-5")
        self.gemini_tts_model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
        self.gemini_tts_voice = os.environ.get("GEMINI_TTS_VOICE", "Kore")

        # Bloques a sintetizar al subir (arranque, RNF-1); el resto bajo demanda (A6).
        self.warmup_blocks = int(os.environ.get("LYP_WARMUP_BLOCKS", "8"))
        # Síntesis TTS en paralelo (A13): baja el arranque de ~40s a ~10s.
        self.tts_concurrency = int(os.environ.get("LYP_TTS_CONCURRENCY", "4"))
        # Tarifas orientativas para el contador de coste (céntimos de € por millón de chars).
        self.tts_rate_cents_per_mchar = float(os.environ.get("LYP_TTS_RATE", "1600"))
        self.llm_rate_cents_per_mchar = float(os.environ.get("LYP_LLM_RATE", "80"))


settings = Settings()
