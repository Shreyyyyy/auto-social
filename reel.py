# /// script
# requires-python = ">=3.11"
# dependencies = ["gradio>=5", "requests", "python-dotenv", "opencv-python-headless", "numpy"]
# ///
"""Prompt -> 30s Gen-Z motion-graphics Hindi AI-explainer Reel -> Buffer.
Claude (script + typed visual per line) -> Gemini TTS -> Lyria 3 music (both with your GEMINI_API_KEY)
-> Coverr stock video + Coverr stills animated with cv2 -> Remotion template render (video/).
Gemini + Google Search does the research (news, facts, SEO keywords); every reel ships with an SEO pack.

  ./start.sh                  # web UI
  ./start.sh make "topic..."  # just render a reel
  ./start.sh auto             # next episode of the latest series -> render -> Buffer (for cron)
  ./start.sh channels         # list Buffer channel ids
  ./start.sh resume out/<run> # finish a failed run, reusing what's done
"""
import base64, fcntl, hashlib, io, json, os, re, shutil, subprocess, sys, time, wave
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
E = os.getenv
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"
GKEY = lambda: {"x-goog-api-key": E("GEMINI_API_KEY", "")}  # header, so the key never appears in URLs, errors or logs
TTS_MODEL = E("TTS_MODEL", "gemini-2.5-flash-preview-tts")
MUSIC_MODEL = E("MUSIC_MODEL", "lyria-3-clip-preview")
RESEARCH_MODEL = E("RESEARCH_MODEL", "gemini-3.8-flash")  # with Google Search grounding
TARGET = float(E("TARGET_SECONDS", "30"))
OUT, SERIES = Path("out"), Path("series")

# Recurring hosts: facecam photo in assets/<name>.png + Google TTS voice.
CAST = {
    "Priya": ("27-year-old Indian woman, software engineer from Indore living in Bengaluru", "Aoede"),
    "Uncle": ("58-year-old Sharma Uncle, kirana store owner from Lucknow", "Algenib"),
}

PSYCH = """AUDIENCE PSYCHOLOGY (use deliberately):
- First 1.5s: pattern interrupt + curiosity gap. Open mid-action or with a claim that sounds wrong but is true.
  Never "aaj hum seekhenge".
- Self-relevance within 5s: tie it to the viewer's phone, money, family, job, safety or status.
- One vivid, concrete desi example beats three facts. It must make the idea click so well that the viewer
  could explain it to someone else in one sentence - that is what makes people share.
- Open a loop early and pay it off around 70% of the runtime (watch-time).
- Conflict: Uncle's doubt voices the audience's doubt; Priya wins with the example, never with jargon.
- Make the viewer feel smart (identity payoff: "ab aap 90% logon se zyada jaante ho").
- One quotable, shareable punchline ("ye video us uncle ko bhejo").
- In a series, end on an open loop to the next episode (Zeigarnik effect).
- Why now: link it to something people are seeing in the news or on their feed right now."""

BEAT = ("brief = a timed beat sheet for a ~30s reel, one line per beat, e.g. '0-2s HOOK: ...', '2-8s ...', ..., "
        "'26-30s PAYOFF + TEASER: ...', then 'EXAMPLE: <the central desi analogy>', 'PSYCH: <levers used>', "
        "'WHY NOW: <the current news/trend it hooks into>'")

RESEARCH = """You research for a 30-second Hindi Instagram Reel that teaches AI to non-tech Indians.
Use Google Search. Be concise: bullet points, every fact with its date and source name.
1. Latest news (last 60 days), India first, that makes this topic feel urgent right now.
2. 3-5 surprising, verified facts or numbers (with source).
3. What Indians commonly ask, search or get confused about here (real questions).
4. 2 everyday Indian analogies that would make it click instantly.
5. SEO: 8 search phrases people actually type (Hinglish + English), 5 relevant hashtags in active use now,
   and current Instagram Reels SEO / discovery guidance (captions, keywords, hashtags, on-screen text).
EXTRA: """

CAST_LINE = "cast: Priya, a playful, sharp engineer; Sharma Uncle, a sceptical kirana-store owner"

PLAN_ONE = f"""You plan viral Hindi Instagram Reels that teach AI to non-tech Indians ({CAST_LINE}).
Use the RESEARCH NOTES (fresh, from Google Search) for news, facts and keywords - never invent numbers - and turn
the idea into ONE reel plan with a very smart, engaging example.
{PSYCH}
Return title and {BEAT}.
IDEA: """

PLAN_SERIES = f"""You are the showrunner of a daily Hindi Instagram Reels series teaching non-tech Indians ({CAST_LINE}).
Use the RESEARCH NOTES (fresh, from Google Search): the subject's milestones, current news, launches and
controversies, and what Indians are talking about right now. Never invent numbers.
Then plan exactly N_EPISODES daily episodes that tell the story end to end in chronological order: origins,
key breakthroughs, today, what comes next. Group them into arcs. One idea per episode, each building on the
previous one. Even historical episodes open with a current-news hook that makes the old idea feel urgent.
{PSYCH}
For each episode return: title (catchy Hinglish), era (year or period), and {BEAT}.
SUBJECT: """

BRIEF = f"""You are the head writer of a viral Gen-Z Indian Instagram Reels series that teaches AI to
non-tech Indians (parents, shopkeepers, students, homemakers). Write ONE ~{TARGET:.0f}-second reel. It is rendered
as a fast, premium MOTION-GRAPHICS edit (kinetic word-by-word captions, animated diagrams, counters, stock
video, sound FX) with the two hosts shown as facecam bubbles - so think visually.

HOSTS (fixed, recurring - use both, by these exact speaker names):
- Priya: {CAST['Priya'][0]}. Smart, playful, explains with desi analogies, never condescending.
- Uncle: {CAST['Uncle'][0]}. Curious, sceptical, witty one-liners; his doubts are the audience's doubts.

CRAFT
- Pick a format that fits: debate, myth-vs-fact, game show, "POV:", countdown, explain-like-I'm-5, rant.
- One genuinely correct insight, explained through an everyday Indian situation (kirana hisaab, cricket, UPI,
  shaadi, chai, IRCTC tatkal, WhatsApp forwards, mummy ki recipes).
- 8-11 short lines, total spoken words <= 70 so it fits {TARGET:.0f}s. Punchy and conversational.
- First line = the hook (a claim that sounds wrong-but-true, or a question they can't ignore). Last line:
  punchline + tease the next episode if one is given (open loop), else "Follow karo!".
- If a timed beat sheet is given below, follow its timings, example and psychology exactly.
- text: natural spoken Hindi in Devanagari (what the voice says); English tech words stay English.
- caption: the SAME words in Roman Hinglish (shown as word-by-word captions).
- delivery: acting note for the voice ("shocked", "smug whisper", "fast and excited", "deadpan").
- visual: what animates during this line. Every line gets a different, concrete visual; make abstract ideas visible:
  hook    - title (<=5 words, can end with an emoji) + emoji. Use for line 1.
  flow    - title + items (2-5 short steps of a process, appear one by one with arrows), e.g. SMS -> words gino -> SPAM
  counter - number (counts up) + suffix (e.g. " Cr", "%") + title (what it counts). Only real, sourced numbers.
  compare - title + items [left, right] (two things side by side with VS)
  stamp   - title + good (true = ✅, false = ❌) - for verdicts and myth-busting
  list    - title + items (2-4 short points)
  video   - query (2-4 English words for a STOCK VIDEO search, real-world scene e.g. "indian street food", "phone
            notifications", "busy office") + title (a short label). Use 1-3 of these to keep it cinematic.
  image   - query (2-3 English words for a STOCK still, animated on screen) + title
  emoji   - emoji + title (a reaction moment)
  quote   - title (the quotable punchline, highlighted)
  All on-screen text in Roman Hinglish, max 6 words.
- punchline: <= 5 words for the end card. cta: e.g. "Part 2 kal ➜" or "Follow for more ➜".
- music_mood: background music style for this reel (e.g. "playful lo-fi with tabla", "tense synth thriller").
- Use the RESEARCH NOTES for facts, numbers and the "why now"; never invent numbers.

SEO (Instagram search + recommendations read captions, on-screen text and the spoken audio):
- Pick ONE main search keyword from the research. Say it in the first spoken line, put it in the hook title,
  and start caption_ig with it.
- caption_ig: line 1 = keyword-rich hook, under 125 characters (visible before "more"); then 2-3 short lines of
  value in Hinglish with 2-3 more search phrases worked in naturally; end with a save/share CTA
  ("Save karo", "Us dost ko bhejo jo..."). NO hashtags in caption_ig.
- seo.keywords: 5-8 search phrases people type (Hinglish + English).
- seo.hashtags: 3-5 tightly relevant hashtags (1 broad, 2-3 niche, 1 series tag), each starting with #.
- seo.alt_text: one plain sentence describing the reel, containing the main keyword.
- seo.first_comment: a question that makes people reply (e.g. "Aapke phone pe aaj kitne spam aaye? 👇").

{PSYCH}

RESEARCH NOTES:
RESEARCH_NOTES

TOPIC / BEAT SHEET: """


class Visual(BaseModel):
    type: Literal["hook", "flow", "counter", "compare", "stamp", "list", "video", "image", "emoji", "quote"]
    title: str = ""
    items: list[str] = []
    number: float = 0
    suffix: str = ""
    emoji: str = ""
    good: bool = True
    query: str = ""


class Line(BaseModel):
    speaker: Literal["Priya", "Uncle"]
    text: str
    caption: str
    delivery: str
    visual: Visual


class Seo(BaseModel):
    keywords: list[str]
    hashtags: list[str]
    alt_text: str
    first_comment: str


class Reel(BaseModel):
    title: str
    genre: str
    music_mood: str
    punchline: str
    cta: str
    caption_ig: str
    seo: Seo
    lines: list[Line]


class Plan(BaseModel):
    title: str
    brief: str


class Episode(BaseModel):
    title: str
    era: str
    brief: str


class Series(BaseModel):
    name: str
    episodes: list[Episode]


def retry(fn, *a, tries=4, **k):
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception as e:
            if i == tries - 1: raise
            print(f"  retry {i + 1}: {e}"); time.sleep(5 * (i + 1))


CLAUDE_AVAILABLE = True


def ask_gemini(prompt, schema):
    """Gemini fallback when Claude CLI hits session rate limits."""
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    p = f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{schema_json}"
    body = {
        "contents": [{"parts": [{"text": p}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    r = requests.post(f"{GEMINI}/gemini-2.5-flash:generateContent", headers=GKEY(), json=body, timeout=120).json()
    if r.get("error"):
        raise RuntimeError(f"Gemini API error: {r['error']}")
    raw = r["candidates"][0]["content"]["parts"][0]["text"]
    return schema.model_validate(json.loads(raw))


def ask(prompt, schema, research=False):
    """Claude Code (subscription), with automatic Gemini 2.5 Flash fallback when Claude limits are reached."""
    global CLAUDE_AVAILABLE
    if E("LLM_PROVIDER", "").lower() == "gemini" or not CLAUDE_AVAILABLE:
        return ask_gemini(prompt, schema)

    try:
        tools = "WebSearch,WebFetch" if research else ""
        out = subprocess.run(["claude", "-p", "--output-format", "json", "--no-session-persistence", "--tools", tools,
                              *(["--allowedTools", tools] if research else []),
                              "--json-schema", json.dumps(schema.model_json_schema()),
                              *(["--model", E("CLAUDE_MODEL")] if E("CLAUDE_MODEL") else [])],
                             input=prompt, capture_output=True, text=True, check=True).stdout
        return schema.model_validate(json.loads(out)["structured_output"])
    except Exception:
        CLAUDE_AVAILABLE = False
        print("⚡ Claude session limit reached. Automatically switching to Gemini 2.5 Flash fallback.")
        return ask_gemini(prompt, schema)


def save_wav(path, pcm, rate=24000):
    with wave.open(str(path), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def gemini(model, parts, **config):
    """Gemini API (REST) -> (mime, bytes) of the first media part."""
    r = requests.post(f"{GEMINI}/{model}:generateContent", headers=GKEY(), timeout=300,
                      json={"contents": [{"parts": parts}], "generationConfig": config}).json()
    for p in ((r.get("candidates") or [{}])[0].get("content") or {}).get("parts", []):
        if "inlineData" in p: return p["inlineData"]["mimeType"], base64.b64decode(p["inlineData"]["data"])
    raise RuntimeError(f"{model}: {str(r.get('error') or r)[:300]}")


def research(topic, extra=""):
    """Gemini + Google Search grounding -> concise research notes with sources (news, facts, analogies, SEO)."""
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=300,
                      json={"contents": [{"parts": [{"text": RESEARCH + extra + "\nTOPIC: " + topic}]}], "tools": [{"google_search": {}}]}).json()
    c = (r.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []))
    if not text: raise RuntimeError(f"research: {str(r.get('error') or r)[:300]}")
    src = [g["web"].get("title", "") for g in c.get("groundingMetadata", {}).get("groundingChunks", []) if "web" in g]
    return text + ("\nSources: " + ", ".join(dict.fromkeys(src)) if src else "")


def google_tts(line, path):
    """Google Cloud Text-to-Speech, Chirp 3 HD Hindi voice (needs the Cloud TTS API enabled for this key)."""
    r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize", headers=GKEY(), timeout=120,
                      json={"input": {"text": line.text}, "voice": {"languageCode": "hi-IN", "name": f"hi-IN-Chirp3-HD-{CAST[line.speaker][1]}"},
                            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}).json()
    if "audioContent" not in r: raise PermissionError(str(r.get("error", r))[:200])
    with wave.open(io.BytesIO(base64.b64decode(r["audioContent"]))) as w: save_wav(path, w.readframes(w.getnframes()))


CLOUD_TTS = E("TTS_ENGINE", "google") == "google"


def voice(line, path):
    """Google Cloud TTS (Chirp 3 HD) when enabled, else Gemini TTS (follows the acting note)."""
    global CLOUD_TTS
    if CLOUD_TTS:
        try: return google_tts(line, path)
        except PermissionError as e: CLOUD_TTS = False; print(f"  Google Cloud TTS unavailable ({str(e)[:90]}) -> Gemini TTS")
    return gemini_tts(line, path)


def gemini_tts(line, path):
    """Gemini TTS, one call per line with that host's voice and acting note. Falls back if acting note triggers finishReason: OTHER."""
    voice_name = CAST[line.speaker][1]
    attempts = [
        f"Say in natural, quick, expressive Hindi: {line.text}",
        line.text,
        line.caption,
    ]
    last_err = None
    for text in attempts:
        try:
            _, pcm = gemini(TTS_MODEL, [{"text": text}],
                            responseModalities=["AUDIO"], speechConfig={"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}})
            save_wav(path, pcm)  # raw 24kHz 16-bit mono PCM
            return
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise last_err


def music(mood, d):
    """Lyria 3: 30s instrumental for this reel's mood (or your own music.mp3 if present). Returns the file name."""
    if Path("music.mp3").exists(): shutil.copy("music.mp3", d / "music.mp3"); return "music.mp3"
    mime, data = gemini(MUSIC_MODEL, [{"text": f"30-second instrumental background track for a fast, playful Instagram reel: {mood}. "
                                                "No vocals, steady energy, loopable."}])
    name = "music.wav" if "wav" in mime else "music.mp3"
    (d / name).write_bytes(data)
    return name


def coverr(query):
    """Coverr search; Coverr matches all words, so fall back to single words (longest first)."""
    for q in [query, *sorted(query.split(), key=len, reverse=True)]:
        hits = requests.get("https://api.coverr.co/videos", timeout=30, headers={"Authorization": f"Bearer {E('COVERR_KEY')}"},
                            params={"query": q, "page_size": 5, "urls": "true"}).json().get("hits", [])
        if hits: return hits
    raise RuntimeError(f"nothing on Coverr for '{query}'")


def stock_video(query, path, secs):
    """Coverr free stock video -> 1080x1026 clip (matches the template's card)."""
    h = max(coverr(query)[:5], key=lambda x: x.get("is_vertical", False))
    raw = path.with_suffix(".src.mp4"); raw.write_bytes(requests.get(h["urls"]["mp4"], timeout=120).content)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(min(2, float(h["duration"]) / 4)), "-i", str(raw), "-t", f"{secs + 1:.1f}",
                    "-vf", "scale=-2:1026,crop=1080:1026,eq=contrast=1.08:saturation=1.25", "-an", "-c:v", "libx264", "-crf", "20", str(path)], check=True)
    raw.unlink()


def grade(img, w, h):
    """cv2 brand grade: cover-crop, local contrast, punchy colour, neon duotone wash, glow, vignette."""
    s = max(w / img.shape[1], h / img.shape[0])
    img = cv2.resize(img, (int(img.shape[1] * s) + 1, int(img.shape[0] * s) + 1), interpolation=cv2.INTER_CUBIC)
    y, x = (img.shape[0] - h) // 2, (img.shape[1] - w) // 2; img = img[y:y + h, x:x + w]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB); lab[..., 0] = cv2.createCLAHE(2.5, (8, 8)).apply(lab[..., 0])
    hsv = cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.35, 0, 255)
    img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    g = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)[..., None] / 255
    duo = (1 - g) * np.array([60, 20, 30], np.float32) + g * np.array([0, 255, 198], np.float32)  # deep purple -> neon lime (BGR)
    img = img * 0.8 + duo * 0.2 + cv2.GaussianBlur(img, (0, 0), 25) * 0.1
    yy, xx = np.mgrid[0:h, 0:w]; vig = 1 - 0.55 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    return img * vig[..., None]


def stock_image(query, path, secs, seed=0):
    """Coverr still (video poster) -> cv2 animation: graded, eased push-in + drift, light sweep, RGB-glitch intro,
    living film grain -> 1080x1026 mp4."""
    hit = coverr(query)[seed % 3 if seed else 0]
    img = cv2.imdecode(np.frombuffer(requests.get(hit["poster"], timeout=60).content, np.uint8), cv2.IMREAD_COLOR)
    if img is None: raise RuntimeError(f"bad Coverr still for '{query}'")
    W, H, n = 1300, 1235, int((secs + 1) * 30)
    base, rng, pan = grade(img, W, H), np.random.default_rng(seed), (-1) ** seed
    grain = rng.normal(0, 7, (H + 64, W + 64, 1)).astype(np.float32)
    xx = np.arange(1080, dtype=np.float32)[None, :] + 0.5 * np.arange(1026, dtype=np.float32)[:, None]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1080x1026", "-r", "30",
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(path)], stdin=subprocess.PIPE)
    for f in range(n):
        e = 1 - (1 - f / max(n - 1, 1)) ** 3  # ease-out
        z = 1 + 0.16 * e; cw, ch = int(W / z / 1.2), int(H / z / 1.2)
        cx = int((W - cw) / 2 + pan * e * (W - cw) * 0.35); cy = int((H - ch) / 2 - e * (H - ch) * 0.15)
        fr = cv2.resize(base[cy:cy + ch, cx:cx + cw], (1080, 1026), interpolation=cv2.INTER_LINEAR)
        sweep = -500 + (f / 30) * 2400  # diagonal light sweep in the first ~0.9s
        if sweep < 1700: fr += 70 * np.exp(-((xx - sweep) / 120) ** 2)[..., None]
        if f < 5:  # RGB-split glitch intro
            k = (5 - f) * 7; fr[..., 0] = np.roll(fr[..., 0], k, 1); fr[..., 2] = np.roll(fr[..., 2], -k, 1)
        oy, ox = rng.integers(0, 64, 2)
        fr += grain[oy:oy + 1026, ox:ox + 1080]
        ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()


def host_photo(name, path):
    """assets/<name>.png if present, else a cv2-drawn gradient avatar with the initial."""
    src = Path("assets") / f"{name.lower()}.png"
    if src.exists(): return shutil.copy(src, path)
    a = np.zeros((400, 400, 3), np.uint8); a[:] = (246, 92, 139) if name == "Priya" else (0, 214, 255)
    cv2.putText(a, name[0], (110, 290), cv2.FONT_HERSHEY_DUPLEX, 7, (18, 11, 11), 18, cv2.LINE_AA); cv2.imwrite(str(path), a)


SFX = {  # synthesised once into assets/sfx - no downloads needed
    "pop": "aevalsrc='0.8*sin(2*PI*(400+2600*t)*t)*exp(-28*t)':d=0.15",
    "whoosh": "anoisesrc=d=0.45:c=pink:a=0.7,bandpass=f=1500:w=1400,afade=t=in:d=0.22,afade=t=out:st=0.22:d=0.23",
    "ding": "aevalsrc='0.5*sin(2*PI*1568*t)*exp(-5*t)+0.3*sin(2*PI*2349*t)*exp(-7*t)':d=0.9",
    "boom": "aevalsrc='0.9*sin(2*PI*(45+140*exp(-12*t))*t)*exp(-3.5*t)':d=0.8",
    "tick": "aevalsrc='0.6*sin(2*PI*2600*t)*exp(-90*t)':d=0.05",
}


def timeline(reel, d):
    """Concatenate line audio -> voice.wav; exact line timings, estimated word timings, visual beat times, SFX cues."""
    t, pcm, lines, sfx = 0.3, b"", [], [[0.3, "boom"]]
    talk = sum(wave.open(str(d / f"line{i}.wav")).getnframes() for i in range(len(reel.lines))) / 24000
    tempo = min(1.2, max(1.0, talk / (TARGET - 0.15 * len(reel.lines) - 1.8)))  # speed up a little if over target
    for i, l in enumerate(reel.lines):
        src = d / f"line{i}.wav"
        if tempo > 1.01:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={tempo:.3f}", "-ar", "24000", "-ac", "1",
                            str(d / f"line{i}.fast.wav")], check=True); src = d / f"line{i}.fast.wav"
        with wave.open(str(src)) as w: data = w.readframes(w.getnframes())
        dur, words = len(data) / 48000, l.caption.split()
        wt = [len(x) + 3 for x in words]
        v, n = l.visual.model_dump(), max(len(l.visual.items), 1)
        v["times"] = ([round(t + 0.1 + k * dur * 0.85 / n, 2) for k in range(n)] if v["type"] in ("flow", "list")
                      else [round(t + 0.1, 2), round(t + dur * 0.45, 2)] if v["type"] == "compare" else [round(t + dur * 0.5, 2)])
        sfx += [[t, "whoosh"]] * (i > 0) + [[x, "pop"] for x in v["times"]] * (v["type"] in ("flow", "list", "compare")) \
            + [[v["times"][0], "ding" if v["good"] else "boom"]] * (v["type"] == "stamp") \
            + [[round(t + k * 0.12, 2), "tick"] for k in range(int(dur * 0.7 / 0.12))] * (v["type"] == "counter") \
            + [[round(t + 0.15, 2), "pop"]] * (v["type"] in ("emoji", "hook", "image", "video"))
        lines.append({"speaker": l.speaker, "start": round(t, 2), "end": round(t + dur, 2), "v": v,
                      "words": [[x, round(t + dur * sum(wt[:k]) / sum(wt), 2)] for k, x in enumerate(words)]})
        pcm += data + b"\0\0" * int(24000 * 0.15); t += dur + 0.15
    save_wav(d / "voice.wav", b"\0\0" * 7200 + pcm)
    dur = round(t + 1.5, 2)
    return lines, sfx + [[dur - 1.3, "ding"]], dur


def make(brief, meta=None, d=None):
    """Script -> voices -> music + stock media -> Remotion render. Pass d=<out dir> to resume a failed run."""
    _l = lock()
    d = Path(d) if d else OUT / time.strftime("%Y%m%d-%H%M%S"); pub = d / "public"
    for sub in ("img", "clip", "sfx"): (pub / sub).mkdir(parents=True, exist_ok=True)
    if (d / "script.json").exists():
        reel = Reel.model_validate_json((d / "script.json").read_text())
        brief = (d / "brief.txt").read_text() if (d / "brief.txt").exists() else brief
        meta = meta or json.loads((d / "job.json").read_text() if (d / "job.json").exists() else "{}")
    else:
        (d / "brief.txt").write_text(brief); (d / "job.json").write_text(json.dumps(meta or {}))
        t0 = time.time(); print("researching (Gemini + Google Search)...")
        try: notes = research(brief[:1500])
        except Exception as e: notes = "(research unavailable)"; print(f"  research skipped: {e}")
        (d / "research.txt").write_text(notes, encoding="utf-8"); print(f"  {time.time() - t0:.0f}s")
        t0 = time.time(); print("writing (Claude)..."); reel = retry(ask, BRIEF.replace("RESEARCH_NOTES", notes) + brief, Reel, tries=2)
        (d / "script.json").write_text(reel.model_dump_json(indent=2), encoding="utf-8"); print(f"  {time.time() - t0:.0f}s")
    print(f"  {reel.title} | {reel.genre}")
    t0 = time.time()
    for i, l in enumerate(reel.lines):
        print(f"voice {i + 1}/{len(reel.lines)}: {l.caption}")
        if not (d / f"line{i}.wav").exists(): retry(voice, l, d / f"line{i}.wav")
    lines, sfx, dur = timeline(reel, d)
    shutil.copy(d / "voice.wav", pub / "voice.wav")
    for n in CAST: host_photo(n, pub / "img" / f"{n.lower()}.png")
    for i, l in enumerate(lines):  # stock media; on failure the line falls back to an emoji visual
        v = l["v"]
        try:
            if v["type"] == "video":
                if not (pub / "clip" / f"{i}.mp4").exists(): stock_video(v["query"], pub / "clip" / f"{i}.mp4", l["end"] - l["start"])
                v["src"] = f"clip/{i}.mp4"
            elif v["type"] == "image":  # Coverr still animated with cv2, played like a clip
                if not (pub / "clip" / f"{i}.mp4").exists(): stock_image(v["query"], pub / "clip" / f"{i}.mp4", l["end"] - l["start"], i)
                v.update(type="video", src=f"clip/{i}.mp4")
        except Exception as e:
            print(f"  {v['type']} '{v['query']}' skipped: {e}"); v.update(type="emoji", emoji=v["emoji"] or "🤔")
    try: mus = (pub / "music.mp3").exists() and "music.mp3" or (pub / "music.wav").exists() and "music.wav" or music(reel.music_mood, pub)
    except Exception as e: print(f"  music skipped: {e}"); mus = ""
    Path("assets/sfx").mkdir(parents=True, exist_ok=True)
    for k, src in SFX.items():
        if not (f := Path(f"assets/sfx/{k}.wav")).exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, "-ar", "44100", "-ac", "1", str(f)], check=True)
        shutil.copy(f, pub / "sfx" / f"{k}.wav")
    print(f"  assets {time.time() - t0:.0f}s")
    props = {"duration": dur, "lines": lines, "sfx": sfx, "voice": "voice.wav", "music": mus, "punchline": reel.punchline,
             "cta": reel.cta, "hosts": {n: f"img/{n.lower()}.png" for n in CAST}}
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    t0 = time.time(); print(f"rendering {dur}s (Remotion)...")
    subprocess.run(["npx", "remotion", "render", "src/index.tsx", "Reel", str((d / "reel.mp4").resolve()), "--log=error",
                    f"--props={(d / 'props.json').resolve()}", f"--public-dir={pub.resolve()}", f"--concurrency={os.cpu_count()}"],
                   cwd="video", check=True)
    print(f"  render {time.time() - t0:.0f}s")
    caption = (reel.caption_ig.strip() + "\n\n" + " ".join(h if h.startswith("#") else "#" + h for h in reel.seo.hashtags[:5])
               + ("\n🎥 Visuals: coverr.co" if any(l["v"]["type"] == "video" for l in lines) else ""))
    meta = {"title": reel.title, "genre": reel.genre, "brief": brief, "caption": caption, "posted": False,
            "first_comment": reel.seo.first_comment, "keywords": reel.seo.keywords, "alt_text": reel.seo.alt_text} | (meta or {})
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done:", d / "reel.mp4")
    return str(d / "reel.mp4"), caption


def upload_cloudinary(video):
    import hashlib
    m = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", E("CLOUDINARY_URL"))
    if not m: raise RuntimeError("CLOUDINARY_URL format must be cloudinary://<api_key>:<api_secret>@<cloud_name>")
    key, secret, cloud_name = m.groups()
    ts = str(int(time.time()))
    sig = hashlib.sha1(f"timestamp={ts}{secret}".encode()).hexdigest()
    with open(video, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/video/upload",
            data={"api_key": key, "timestamp": ts, "signature": sig},
            files={"file": f},
            timeout=300
        ).json()
    if "secure_url" in r:
        return r["secure_url"]
    raise RuntimeError(f"Cloudinary upload failed: {r}")


def upload(video):
    """Buffer needs a public, permanent video URL. Uses Cloudinary if CLOUDINARY_URL set, else falls back to catbox.moe."""
    if E("CLOUDINARY_URL"):
        return upload_cloudinary(video)
    with open(video, "rb") as f:
        url = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, timeout=600,
                            files={"fileToUpload": ("reel.mp4", f, "video/mp4")},
                            headers={"User-Agent": "Mozilla/5.0 auto-social"}).text.strip()
    if not url.startswith("https://"): raise RuntimeError(f"catbox upload failed: {url[:300]}")
    return url


def buffer(query, **variables):
    r = requests.post("https://api.buffer.com", json={"query": query, "variables": variables},
                      headers={"Authorization": f"Bearer {E('BUFFER_TOKEN')}"}).json()
    if r.get("errors"): raise RuntimeError(f"Buffer: {r['errors'][0]['message']}")
    return r["data"]


def fingerprint(video):
    return hashlib.sha256(Path(video).read_bytes()).hexdigest()[:16]


def already_posted(fp):
    """Duplicate guard: has this exact video file already been sent to Buffer from any run?"""
    for f in OUT.glob("*/meta.json"):
        j = json.loads(f.read_text())
        if j.get("posted") and j.get("fingerprint") == fp: return f.parent.name
    return None


def set_status(video, **kv):
    m = Path(video).parent / "meta.json"
    j = json.loads(m.read_text()) | kv; m.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    return j


def approve(video, caption):
    """Explicit human approval of THIS video + caption (required before any scheduled job may post it)."""
    j = set_status(video, status="approved", caption=caption, fingerprint=fingerprint(video), approved_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    if j.get("series"): sr = load(j["series"]); sr["episodes"][j["ep"] - 1]["status"] = "approved"; save(sr)
    return f"✅ Approved for posting: {j['title']}"


def post(video, caption):
    """Queue the reel in Buffer (BUFFER_MODE=addToQueue uses your Buffer schedule; shareNow posts immediately).
    The SEO first comment (engagement question) is posted with it. Refuses duplicates."""
    m = Path(video).parent / "meta.json"
    fp = fingerprint(video)
    if (dup := already_posted(fp)): raise RuntimeError(f"already sent to Buffer from run {dup} - not posting it twice")
    ig = {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}
    if m.exists() and json.loads(m.read_text()).get("first_comment"): ig["firstComment"] = json.loads(m.read_text())["first_comment"]
    p = buffer("""mutation($input: CreatePostInput!) { createPost(input: $input) {
        ... on PostActionSuccess { post { id } } ... on MutationError { message } } }""", input={
        "text": caption, "channelId": E("BUFFER_CHANNEL_ID"), "schedulingType": "automatic",
        "mode": E("BUFFER_MODE", "addToQueue"),
        "assets": [{"video": {"url": upload(video), "metadata": {"thumbnailOffset": 1000}}}],
        "metadata": {"instagram": ig}})["createPost"]
    if "post" not in p:
        if m.exists(): set_status(video, status="failed", error=str(p.get("message", p))[:300])
        raise RuntimeError(f"Buffer: {p.get('message', p)}")
    if m.exists():  # remember it in history / series
        j = set_status(video, posted=True, status="queued", fingerprint=fp, buffer_post_id=p["post"]["id"],
                       caption=caption, posted_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        if j.get("series"):
            sr = load(j["series"]); sr["episodes"][j["ep"] - 1]["status"] = "posted"; save(sr)
    return f"✅ Sent to Buffer ({E('BUFFER_MODE', 'addToQueue')}) - post id {p['post']['id']}"


def channels():
    for o in buffer("{ account { organizations { id name } } }")["account"]["organizations"]:
        for c in buffer("query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service } }", o=o["id"])["channels"]:
            print(f"{c['service']:10} {c['name']:25} BUFFER_CHANNEL_ID={c['id']}")


def slug(name):
    return re.sub(r"\W+", "-", name.lower()).strip("-")[:60]


def load(sid):
    return json.loads((SERIES / f"{sid}.json").read_text())


def save(sr):
    SERIES.mkdir(exist_ok=True)
    (SERIES / f"{sr['id']}.json").write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")


def plan_series(subject, n):
    notes = research(subject, "6. Key milestones from the origins to today and what is coming next: year, who, what changed, "
                              "why it mattered - enough for N daily episodes.\n".replace("N", str(int(n))))
    sr = ask(PLAN_SERIES.replace("N_EPISODES", str(int(n))) + "\nRESEARCH NOTES:\n" + notes + "\n\n" + subject, Series)
    sr = {"id": slug(sr.name), "name": sr.name, "subject": subject,
          "episodes": [e.model_dump() | {"status": "planned"} for e in sr.episodes]}
    save(sr)
    return sr


def make_episode(sr, i):
    eps, e = sr["episodes"], sr["episodes"][i]
    nxt = f"\nNEXT EPISODE (tease it): {eps[i + 1]['title']}" if i + 1 < len(eps) else "\nThis is the series finale."
    video, cap = make(f"Series '{sr['name']}', episode {i + 1}/{len(eps)}: {e['title']} ({e['era']})\n{e['brief']}{nxt}",
                      {"title": f"#{i + 1} {e['title']}", "series": sr["id"], "ep": i + 1})
    e.update(status="generated", video=video); save(sr)
    return video, cap


_LOCK = []


class lock:
    """One job at a time across processes (cron vs UI vs CLI); re-entrant within a process."""
    def __init__(self):
        self.f = None
        if _LOCK: return
        self.f = open(".reel.lock", "w")
        try: fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: self.f.close(); raise RuntimeError("another reel job is running - try again when it finishes")
        _LOCK.append(self)

    def __del__(self):
        if self.f: _LOCK.clear(); self.f.close()


def auto():
    """Cron, approval-gated: posts the next episode ONLY if you approved that exact video in the UI.
    If the next episode isn't made yet, it is generated and left 'awaiting approval' - never posted silently."""
    _l = lock()
    files = sorted(SERIES.glob("*.json"), key=lambda f: f.stat().st_mtime)
    if not files: return print("No series yet - plan one in the UI first.")
    sr = load(E("SERIES") or files[-1].stem)
    i = next((i for i, e in enumerate(sr["episodes"]) if e["status"] != "posted"), None)
    if i is None: return print(f"'{sr['name']}' is fully posted.")
    e = sr["episodes"][i]
    if e["status"] == "planned":
        video, _ = make_episode(sr, i)
        return print(f"Episode {i + 1} generated -> awaiting your approval in the UI (History tab): {video}")
    meta = json.loads((Path(e["video"]).parent / "meta.json").read_text())
    if meta.get("status") != "approved" or meta.get("fingerprint") != fingerprint(e["video"]):
        return print(f"Episode {i + 1} is waiting for approval - not posting. Approve it in the History tab.")
    print(post(e["video"], meta["caption"]))


def history():
    rows = []
    for m in sorted(OUT.glob("*/meta.json"), reverse=True):
        j = json.loads(m.read_text())
        st = "📤 queued" if j.get("posted") else {"approved": "✅ approved", "failed": "❌ failed"}.get(j.get("status"), "🕒 awaiting approval")
        rows.append([m.parent.name, j["title"], j.get("series", "-"), st])
    return rows


def ui():
    import gradio as gr

    def ep_rows(sid):
        return [[i + 1, e["era"], e["title"], e["status"]] for i, e in enumerate(load(sid)["episodes"])] if sid else []

    def series_ids():
        return [(load(f.stem)["name"], f.stem) for f in sorted(SERIES.glob("*.json"))]

    def guard(fn):  # show the real error in the UI instead of a bare "Error"
        def run(*a):
            try: return fn(*a)
            except Exception as e: raise gr.Error(f"{type(e).__name__}: {e}", duration=None)
        return run

    def safe_post(path, cap):  # clicking Post = explicit approval of this exact video + caption
        if not path: return "❌ Generate or pick a reel first"
        try: approve(path, cap); return post(path, cap)
        except Exception as e: return f"❌ {type(e).__name__}: {e}"

    def safe_approve(path, cap):
        if not path: return "❌ Pick a reel first"
        try: return approve(path, cap) + " - the scheduled job may now post it"
        except Exception as e: return f"❌ {type(e).__name__}: {e}"

    def plan_one(idea):
        p = ask(PLAN_ONE + "\nRESEARCH NOTES:\n" + research(idea) + "\n\n" + idea, Plan)
        return f"{p.title}\n\n{p.brief}"

    def gen_one(brief):
        v, c = make(brief)
        return v, c, v, history()

    def plan_s(subject, n):
        sr = plan_series(subject, n)
        return gr.update(choices=series_ids(), value=sr["id"]), ep_rows(sr["id"])

    def gen_s(sid, x):
        sr, log = load(sid), ""
        todo = [i for i, e in enumerate(sr["episodes"]) if e["status"] == "planned"][:int(x)]
        for k, i in enumerate(todo):
            log += f"⏳ {k + 1}/{len(todo)} - episode {i + 1}: {sr['episodes'][i]['title']}\n\n"
            yield log, ep_rows(sid)
            try: make_episode(sr, i)
            except Exception as e:
                yield log + f"❌ episode {i + 1} failed: {type(e).__name__}: {e}", ep_rows(sid); return
            log += f"✅ episode {i + 1} done\n\n"
            yield log, ep_rows(sid)
        yield log + ("🎉 Done - review & post in History" if todo else "Nothing left to generate."), ep_rows(sid)

    def pick_ep(sid, evt: gr.SelectData):
        e = load(sid)["episodes"][evt.index[0]]
        return f"### #{evt.index[0] + 1} {e['title']} · {e['era']} · {e['status']}\n```\n{e['brief']}\n```"

    def pick_run(evt: gr.SelectData):
        d = OUT / history()[evt.index[0]][0]
        return str(d / "reel.mp4"), json.loads((d / "meta.json").read_text())["caption"], str(d / "reel.mp4")

    with gr.Blocks(title="AI Reels Studio") as app:
        gr.Markdown("# 🎬 AI Reels Studio\nGemini researches (Google Search) · Claude writes · Google voices · Lyria scores · Coverr + cv2 visuals · Remotion animates · Buffer posts")
        with gr.Tab("⚡ Single reel"):
            with gr.Row():
                with gr.Column():
                    idea = gr.Textbox(label="One-line idea", placeholder="ChatGPT ko maths mein galti kyun hoti hai?")
                    plan_btn = gr.Button("🧠 Research & plan (with timings)")
                    brief = gr.Textbox(label="Timed beat sheet - edit freely before generating", lines=14)
                    gen_btn = gr.Button("🎬 Generate reel", variant="primary")
                with gr.Column():
                    vid1, cap1, path1 = gr.Video(label="Reel", height=560), gr.Textbox(label="Caption", lines=4), gr.State()
                    post1, status1 = gr.Button("📤 Post via Buffer"), gr.Markdown()
        with gr.Tab("📚 Series / playlist"):
            with gr.Row():
                subject = gr.Textbox(label="Series subject", placeholder="Teaching AI from the very beginning to today", scale=3)
                days = gr.Slider(5, 100, value=30, step=1, label="Episodes (days)", scale=2)
                plan_s_btn = gr.Button("🧠 Research & plan series", scale=1)
            with gr.Row():
                with gr.Column(scale=3):
                    sid = gr.Dropdown(series_ids(), label="Series", interactive=True)
                    eps = gr.Dataframe(headers=["#", "Era", "Title", "Status"], interactive=False, wrap=True)
                with gr.Column(scale=2):
                    ep_detail = gr.Markdown("Click an episode to see its beat sheet.")
                    x = gr.Number(3, label="How many to generate now", minimum=1, maximum=100, precision=0)
                    gen_s_btn = gr.Button("🎬 Generate next X episodes", variant="primary")
                    log = gr.Markdown()
        with gr.Tab("🗂 History") as hist_tab:
            with gr.Row():
                with gr.Column(scale=3):
                    runs = gr.Dataframe(history(), headers=["Run", "Title", "Series", "Status"], interactive=False, wrap=True)
                with gr.Column(scale=2):
                    vid2, cap2, path2 = gr.Video(label="Reel", height=560), gr.Textbox(label="Caption", lines=4), gr.State()
                    with gr.Row():
                        appr2 = gr.Button("✅ Approve for scheduled post")
                        post2 = gr.Button("📤 Post now via Buffer", variant="primary")
                    status2 = gr.Markdown()

        plan_btn.click(guard(plan_one), idea, brief)
        gen_btn.click(guard(gen_one), brief, [vid1, cap1, path1, runs])
        post1.click(safe_post, [path1, cap1], status1)
        plan_s_btn.click(guard(plan_s), [subject, days], [sid, eps])
        sid.change(ep_rows, sid, eps)
        eps.select(pick_ep, sid, ep_detail)
        gen_s_btn.click(gen_s, [sid, x], [log, eps])
        hist_tab.select(history, None, runs)
        runs.select(pick_run, None, [vid2, cap2, path2])
        post2.click(safe_post, [path2, cap2], status2).then(history, None, runs)
        appr2.click(safe_approve, [path2, cap2], status2).then(history, None, runs)
    app.launch(inbrowser=True, theme=gr.themes.Soft(primary_hue="orange"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ui"
    {"ui": ui, "auto": auto, "channels": channels, "make": lambda: make(" ".join(sys.argv[2:])),
     "resume": lambda: make("", d=sys.argv[2])}[cmd]()
