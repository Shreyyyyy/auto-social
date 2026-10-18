# /// script
# requires-python = ">=3.11"
# dependencies = ["mlx-audio", "soundfile", "numpy"]
# ///
"""Local voice engine (Apple silicon, free, no key): POST /tts {"text", "lang", "delivery"} -> WAV.
Runs on the Mac itself - Docker can't use the GPU - and the app calls it (LOCAL_TTS_URL).
  Hindi / English: VoxCPM2 - ONE narrator voice that acts each line's delivery note ("excited", "lowered voice, secret"...)
  other Indian languages: OmniVoice, cloning the same narrator voice
The narrator is designed once from config.json "narrator_voice" into assets/voice/narrator.wav. To use YOUR voice, replace
it with a ~10s recording of yourself and put exactly what you said in assets/voice/narrator.txt.
Picked from a listening test of 12 open TTS models (VoxCPM2 kept one voice with the widest emotion range in Hindi).

  uv run tts_server.py        (./start.sh starts it)
"""
import io, json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import soundfile as sf

VOX, OMNI = "mlx-community/VoxCPM2-8bit", "mlx-community/OmniVoice-bf16"
REF = Path("assets/voice/narrator.wav")
LANGS = {"hi": "Hindi", "en": "English", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
         "ml": "Malayalam", "pa": "Punjabi", "or": "Odia", "as": "Assamese", "ur": "Urdu", "ne": "Nepali"}
C = json.loads(Path("config.json").read_text()) if Path("config.json").exists() else {}
VOICE = C.get("narrator_voice") or ("A young Indian woman in her late twenties, warm, lively and expressive, smiling while she talks, "
                                    "natural conversational Hindi, clear close-mic recording")
MODELS, LOCK = {}, threading.Lock()  # one generation at a time: MLX models are not thread-safe


def synth(repo, **kw):
    from mlx_audio.tts.utils import load_model
    m = MODELS.get(repo) or MODELS.setdefault(repo, load_model(repo))
    return np.concatenate([np.array(r.audio).reshape(-1) for r in m.generate(**kw)]), m.sample_rate


def narrator():
    """The channel's one narrator voice (designed once, or your own recording) -> (wav path, its transcript)."""
    if not REF.exists():
        REF.parent.mkdir(parents=True, exist_ok=True)
        text = "नमस्ते दोस्तों! आज मैं आपको एक बहुत ही मज़ेदार बात बताने वाली हूँ, तो चलिए शुरू करते हैं।"
        a, sr = synth(VOX, text=text, instruct=VOICE)
        sf.write(REF, a, sr); REF.with_suffix(".txt").write_text(text)
    return str(REF), REF.with_suffix(".txt").read_text().strip()


def speak(text, lang="hi", delivery=""):
    with LOCK:
        ref, ref_text = narrator()
        if lang in ("hi", "en"): return synth(VOX, text=text, ref_audio=ref, instruct=delivery or None), "VoxCPM2"
        return synth(OMNI, text=text, language=LANGS.get(lang, lang), ref_audio=ref, ref_text=ref_text), "OmniVoice"


class H(BaseHTTPRequestHandler):
    def do_GET(self):  # health check
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_POST(self):
        try:
            j = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            (a, sr), engine = speak(j["text"], (j.get("lang") or "hi")[:2].lower(), j.get("delivery", ""))
            buf = io.BytesIO(); sf.write(buf, a, sr, format="WAV", subtype="PCM_16")
        except Exception as e:
            self.send_response(500); self.end_headers(); self.wfile.write(f"{type(e).__name__}: {e}".encode()[:500]); return
        self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("X-Engine", engine); self.end_headers()
        self.wfile.write(buf.getvalue())

    def log_message(self, *a): pass


if __name__ == "__main__":
    port = int(os.getenv("TTS_PORT", "8790"))
    print(f"local voice engine on :{port} (first request downloads the models, ~4 GB)", flush=True)
    ThreadingHTTPServer((os.getenv("TTS_HOST", "127.0.0.1"), port), H).serve_forever()
