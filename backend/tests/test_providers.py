"""Contrato de proveedores reales con HTTP simulado (sin API keys)."""
import base64
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_claude_llm_contract(app_env):
    from app.providers.claude_llm import ClaudeLLM

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["x-api-key"] == "test-key"
        assert body["messages"][0]["role"] == "user"
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "texto limpio"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = ClaudeLLM(api_key="test-key", client=client)
    out = llm.clean_block("texto [1] sucio", "Doc", "es")
    assert out.text == "texto limpio"
    assert llm.intro("- Sección 1", "Doc", "es") == "texto limpio"


def test_gemini_tts_contract(app_env):
    from app.providers.gemini_tts import GeminiTTS

    pcm = b"\x00\x00" * 24000  # 1 segundo de silencio s16le mono 24kHz

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["generationConfig"]["responseModalities"] == ["AUDIO"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"inlineData": {"data": base64.b64encode(pcm).decode()}}]}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tts = GeminiTTS(api_key="test-key", client=client)
    res = tts.synthesize("hola mundo", "es")
    assert res.audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"ID")  # MP3 (frame o ID3)
    assert 900 <= res.duration_ms <= 1100
    assert res.chars == len("hola mundo")


def test_espeak_tts_real_audio(app_env):
    from app.providers.espeak_tts import EspeakTTS
    res = EspeakTTS().synthesize("Hola, esto es una prueba de audio real.", "es")
    assert len(res.audio) > 1000
    assert res.duration_ms > 500


def test_registry_selects_by_env(app_env):
    from app.providers import registry
    assert registry.get_llm("fake").name == "fake"
    assert registry.get_tts("espeak").name == "espeak"
    assert registry.get_llm().name == "fake"  # del entorno del fixture
