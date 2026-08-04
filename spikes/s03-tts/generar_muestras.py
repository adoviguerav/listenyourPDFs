#!/usr/bin/env python3
"""Spike S0.3 — genera las muestras de la prueba ciega de voces TTS.

Ejecutar con las API keys en el entorno (las que tengas; salta las que falten):
    OPENAI_API_KEY=sk-...  GEMINI_API_KEY=...  ELEVENLABS_API_KEY=...  python generar_muestras.py

Genera es-*.mp3 / en-*.mp3 por proveedor y un blind-test.html que baraja las
muestras sin decirte cuál es cuál hasta que eliges.

Coste aproximado de ejecutar esto completo: < 0,10 €.
"""
import base64
import json
import os
import random
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).parent
FRAGMENTS = {
    "es": (HERE / "fragmento-es.txt").read_text().strip(),
    "en": (HERE / "fragmento-en.txt").read_text().strip(),
}


def openai_tts(text: str, lang: str) -> bytes:
    req = Request(
        "https://api.openai.com/v1/audio/speech",
        data=json.dumps({
            "model": "gpt-4o-mini-tts",
            "voice": "nova" if lang == "es" else "onyx",
            "input": text,
            "response_format": "mp3",
        }).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    return urlopen(req).read()


def gemini_tts(text: str, lang: str) -> bytes:
    # Gemini TTS devuelve PCM; se convierte a MP3 con ffmpeg fuera si hace falta.
    model = "gemini-2.5-flash-preview-tts"
    req = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={os.environ['GEMINI_API_KEY']}",
        data=json.dumps({
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}},
            },
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    data = json.loads(urlopen(req).read())
    b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    return base64.b64decode(b64)  # PCM 24kHz s16le


def elevenlabs_tts(text: str, lang: str) -> bytes:
    voice = "EXAVITQu4vr4xnSDxMaL"  # Sarah (multilingüe)
    req = Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    return urlopen(req).read()


PROVIDERS = {
    "openai": ("OPENAI_API_KEY", openai_tts, "mp3"),
    "gemini": ("GEMINI_API_KEY", gemini_tts, "pcm"),
    "elevenlabs": ("ELEVENLABS_API_KEY", elevenlabs_tts, "mp3"),
}


def main():
    generated = []
    for name, (env, fn, fmt) in PROVIDERS.items():
        if not os.environ.get(env):
            print(f"SKIP {name}: falta {env}")
            continue
        for lang, text in FRAGMENTS.items():
            out = HERE / f"{lang}-{name}.{'mp3' if fmt == 'mp3' else 'pcm'}"
            out.write_bytes(fn(text, lang))
            if fmt == "pcm":
                os.system(f"ffmpeg -y -loglevel error -f s16le -ar 24000 -ac 1 "
                          f"-i {out} -b:a 64k {out.with_suffix('.mp3')}")
                out.unlink()
                out = out.with_suffix(".mp3")
            generated.append(out.name)
            print(f"OK  {out.name}")

    # espeak de referencia si existe
    for lang in FRAGMENTS:
        ref = HERE / f"{lang}-espeak.mp3"
        if ref.exists():
            generated.append(ref.name)

    build_blind_test(generated)


def build_blind_test(files):
    samples = []
    for f in sorted(files):
        lang, prov = Path(f).stem.split("-", 1)
        b64 = base64.b64encode((HERE / f).read_bytes()).decode()
        samples.append({"lang": lang, "prov": prov,
                        "src": f"data:audio/mpeg;base64,{b64}"})
    random.shuffle(samples)
    html = (HERE / "blind-test-template.html").read_text().replace(
        "__SAMPLES__", json.dumps(samples))
    (HERE / "blind-test.html").write_text(html)
    print(f"\nPrueba ciega: {HERE/'blind-test.html'} — ábrela y elige a oído.")


if __name__ == "__main__":
    main()
