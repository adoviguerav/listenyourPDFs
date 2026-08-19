"""Contrato del proveedor STT (RF-4.1): GeminiSTT con HTTP simulado + FakeSTT.

Mismo patrón que test_providers.py: httpx.MockTransport, sin API keys reales.
"""
import base64
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))


def _inline_data(part: dict) -> dict | None:
    """La API REST de Gemini acepta snake_case y camelCase indistintamente."""
    return part.get("inline_data") or part.get("inlineData")


def test_gemini_stt_contract(app_env):
    from app.providers.gemini_stt import GeminiSTT

    audio = b"\x1aE\xdf\xa3" + b"webm-falso" * 20  # cabecera EBML de webm + relleno

    def handler(request: httpx.Request) -> httpx.Response:
        # Petición bien formada: generateContent con la key en query (como GeminiTTS).
        assert request.url.host == "generativelanguage.googleapis.com"
        assert ":generateContent" in request.url.path
        assert request.url.params["key"] == "test-key"
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        blobs = [p for p in parts if _inline_data(p)]
        assert len(blobs) == 1  # el audio viaja como inline_data
        blob = _inline_data(blobs[0])
        assert blob["data"] == base64.b64encode(audio).decode()
        assert (blob.get("mime_type") or blob.get("mimeType")) == "audio/webm"
        # Debe acompañar un prompt de texto pidiendo la transcripción.
        assert any(p.get("text") for p in parts)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": "¿qué significa el abstract?"}]}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    stt = GeminiSTT(api_key="test-key", client=client)
    out = stt.transcribe(audio, "audio/webm", "es")
    assert out.strip() == "¿qué significa el abstract?"


def test_fake_stt_returns_configured_text_and_records_calls(app_env):
    from app.providers.fakes import FakeSTT

    stt = FakeSTT(text="transcripción fijada")
    # Devuelve siempre el texto configurado, sea cual sea el audio/mime/idioma.
    assert stt.transcribe(b"\x00\x01", "audio/webm", "es") == "transcripción fijada"
    assert stt.transcribe(b"\x02", "audio/ogg", "en") == "transcripción fijada"
    # Registra cada llamada (mismo patrón que FakeLLM/FakeTTS).
    assert len(stt.calls) == 2


def test_registry_selects_stt(app_env):
    from app.providers import registry
    # El registry debe exponer get_stt para que la API resuelva el proveedor (RF-7.4).
    assert registry.get_stt("fake").name == "fake"
