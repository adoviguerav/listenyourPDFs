#!/bin/bash
# Genera el audio de prueba e inyecta el data-URI en la plantilla → spike-s01-audio-ios.html
set -e
cd "$(dirname "$0")"
for i in 1 2 3 4; do cat texto.txt; echo "Minuto de referencia número $i."; done > /tmp/texto-largo.txt
espeak-ng -v es -s 155 -w /tmp/voz.wav -f /tmp/texto-largo.txt
ffmpeg -y -loglevel error -i /tmp/voz.wav -codec:a libmp3lame -b:a 64k -ac 1 /tmp/voz.mp3
python3 - << 'PY'
import base64
b64 = base64.b64encode(open("/tmp/voz.mp3","rb").read()).decode()
html = open("plantilla.html").read().replace("__AUDIO_DATA_URI__", "data:audio/mpeg;base64," + b64)
open("spike-s01-audio-ios.html","w").write(html)
print("OK: spike-s01-audio-ios.html")
PY
