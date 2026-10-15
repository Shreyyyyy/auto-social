# /// script
# requires-python = ">=3.11"
# dependencies = ["gradio>=5", "requests", "python-dotenv", "opencv-python-headless", "numpy"]
# ///
"""Prompt -> ~30s news-explainer Reel (full-screen real footage, burned-in captions) -> Buffer, after your approval.
Niche, audience, language, voice and theme come from config.json.
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
TTS_MODEL = E("TTS_MODEL", "gemini-2.5-pro-preview-tts")  # one emotional take of the whole script
LINE_TTS_MODEL = E("LINE_TTS_MODEL", "gemini-2.5-flash-preview-tts")  # line-by-line fallback
MUSIC_MODEL = E("MUSIC_MODEL", "lyria-3-clip-preview")
RESEARCH_MODEL = E("RESEARCH_MODEL", "gemini-3.8-flash")  # with Google Search grounding; also judges footage relevance
FOOTAGE_MIN_SCORE = float(E("FOOTAGE_MIN_SCORE", "6"))  # below this, a line gets a text scene instead of unrelated footage
OUT, SERIES = Path("out"), Path("series")

# Everything about WHAT the channel is lives in config.json (niche, audience, language, voice, theme...).
C = {"niche": "AI and technology, explained simply", "audience": "a general audience", "region": "India",
     "spoken_language": "natural spoken Hindi in Devanagari, English tech words in English", "caption_language": "Roman-script Hinglish",
     "tts_language_code": "hi-IN", "tone": "smart, playful and credible", "examples": "everyday life", "duration_seconds": 30,
     "voice": "Puck", "voice_style": "a popular creator in their late 20s - warm, quick-witted, genuinely excited",
     "accent": "natural North Indian Hindi; English words said the Indian way", "series_hashtag": "", "fallback_footage": ["city street", "people using smartphone"],
     "theme": {"highlight": "#FFE600", "ink": "#111111"}} | (json.loads(Path("config.json").read_text()) if Path("config.json").exists() else {})
TARGET = float(E("TARGET_SECONDS", C["duration_seconds"]))
CHANNEL = (f"channel context, for tone and audience only (never change the user's topic): {C['niche']}; "
           f"audience: {C['audience']} in {C['region']}")
FORMAT = (f"{CHANNEL}; format: one narrator voice-over over full-screen real stock footage with burned-in captions - "
          "no presenters, characters or faces")

PSYCH = """AUDIENCE PSYCHOLOGY (use deliberately):
- First 1.5s: pattern interrupt + curiosity gap. Open mid-action or with a claim that sounds wrong but is true.
  Never "aaj hum seekhenge".
- Self-relevance within 5s: tie it to the viewer's phone, money, family, job, safety or status.
- One vivid, concrete desi example beats three facts. It must make the idea click so well that the viewer
  could explain it to someone else in one sentence - that is what makes people share.
- Open a loop early and pay it off around 70% of the runtime (watch-time).
- Conflict: voice the viewer's doubt yourself ("Aap soch rahe ho...?") and win with the example, never with jargon.
- Make the viewer feel smart (identity payoff: "ab aap 90% logon se zyada jaante ho").
- One quotable, shareable punchline (e.g. "ye video us dost ko bhejo jo...").
- In a series, end on an open loop to the next episode (Zeigarnik effect).
- Why now: link it to something people are seeing in the news or on their feed right now."""

BEAT = ("brief = a timed beat sheet for a ~30s reel, one line per beat, e.g. '0-2s HOOK: ...', '2-8s ...', ..., "
        "'26-30s PAYOFF + TEASER: ...', then 'EXAMPLE: <the central desi analogy>', 'PSYCH: <levers used>', "
        "'WHY NOW: <the current news/trend it hooks into>'")

RESEARCH = f"""You are the researcher for a {TARGET:.0f}-second Instagram Reel. The reel is about EXACTLY what the USER PROMPT
(at the end) asks - whatever the subject is. ({CHANNEL}.)
Use Google Search. Be concise, bullet points, every fact with its date and source name. Sections:
0. UNDERSTANDING: in 2 lines, what the user wants - the topic, the angle, and the one takeaway the viewer should leave with.
1. LATEST NEWS: what happened in the last 60 days ({C['region']} first) that makes this topic matter right now.
2. TRENDING: how this topic is trending - search interest, viral posts, memes, the angles other creators are using
   on Instagram / YouTube Shorts / X right now, and any hashtag or audio trend attached to it.
3. WHAT PEOPLE ARE SAYING: real questions, opinions, myths, complaints, jokes and slang from comments, Reddit, X,
   Quora, YouTube - quote short real phrasings where you can.
4. FACTS: 3-5 surprising, verified facts or numbers with source + date. Flag numbers that disagree between sources.
5. ANALOGIES: 2 everyday analogies from {C['examples']} that would make it click instantly.
6. SEO: 8 search phrases people actually type about this, 5 relevant hashtags in active use now, and current
   Instagram Reels discovery guidance (captions, keywords, hashtags, on-screen text).
EXTRA: """

PLAN_ONE = f"""You plan viral Instagram Reels ({FORMAT}).
Use the RESEARCH NOTES (fresh, from Google Search) for news, facts and keywords - never invent numbers - and turn
the idea into ONE reel plan with a very smart, engaging example.
{PSYCH}
Return title and {BEAT}.
Plan exactly what this idea asks - never switch to a different topic.
IDEA: """

PLAN_SERIES = f"""You are the showrunner of a daily Instagram Reels series ({FORMAT}).
Use the RESEARCH NOTES (fresh, from Google Search): the subject's milestones, current news, launches and
controversies, and what Indians are talking about right now. Never invent numbers.
Then plan exactly N_EPISODES daily episodes that tell the story end to end in chronological order: origins,
key breakthroughs, today, what comes next. Group them into arcs. One idea per episode, each building on the
previous one. Even historical episodes open with a current-news hook that makes the old idea feel urgent.
{PSYCH}
For each episode return: title (catchy Hinglish), era (year or period), and {BEAT}.
The series is about exactly this subject - never drift to a different one.
SUBJECT: """

BRIEF = f"""You write a fast, credible ~{TARGET:.0f}-second Instagram Reel about EXACTLY the topic in the user's prompt / beat sheet
below - whatever it is; never switch to a different topic. ({CHANNEL}.)
Build it from the RESEARCH NOTES: use what is trending, the real questions and phrasings people use, and the latest news.
FORMAT: ONE narrator voice-over over full-screen REAL stock footage (no presenters, no characters, no faces talking to
camera), bold burned-in captions, and a clean data card only where a number, process or comparison needs it.
It must feel like a real creator's news-explainer edit - nothing that looks AI-generated.
If the beat sheet below mentions characters or presenters, turn their lines into the narrator's voice.

CRAFT
- Tone: {C['tone']}.
- text: what the voice says, in {C['spoken_language']}. caption: the SAME words in {C['caption_language']}.
- One genuinely correct insight, made concrete with an everyday example ({C['examples']}).
- 8-11 short lines, total spoken words <= {int(TARGET * 2.3)}. Punchy and conversational.
- hook: <= 6 words shown big during line 1 - the main keyword + the surprising part.
- Line 1 = the hook (a claim that sounds wrong-but-true, or a question they can't ignore). Last line: payoff +
  tease the next episode if one is given (open loop), else a save/follow CTA.
- If a timed beat sheet is given below, follow its timings, example and psychology.
- delivery: the emotion for this line, 1-4 words, as a voice director would mark it ("shocked", "leaning in, secretive",
  "playful, smiling", "short laugh", "serious, slower", "excited"). Vary it line to line like a real person telling a story.
- footage: 3 STOCK VIDEO search options for this line (2-3 English words each), most specific first, then broader,
  then a simpler scene that still clearly relates - e.g. ["gold jewellery shop", "gold jewellery", "jewellery"].
  Describe what a camera would see (people, places, objects) - never abstract words like AI, algorithm, data.
  A different scene every line. A stock library is generic, so prefer common, filmable subjects.
- visual: an optional clean data card for this line. type "none" for most lines; otherwise
  counter (number + suffix + title; only numbers from the research), flow (title + 2-4 steps),
  compare (title + items [left, right]), stamp (title + good: true = FACT, false = MYTH), list (title + 2-3 items),
  quote (title = the quotable punchline). Use 2-4 cards per reel, never more. Card text max 6 words per item.
- source: if the line states a news fact or number, "Publication · date" from the research notes, else "".
- music_mood: background music style (e.g. "minimal news beat", "warm curious lo-fi", "tense pulse").
- Use the RESEARCH NOTES for facts, numbers and the "why now"; never invent numbers.

SEO (Instagram search + recommendations read captions, on-screen text and the spoken audio):
- Pick ONE main search keyword from the research. Say it in the first spoken line, put it in the hook, and start
  caption_ig with it.
- caption_ig: line 1 = keyword-rich hook, under 125 characters (visible before "more"); then 2-3 short lines of
  value with 2-3 more search phrases worked in naturally; end with a save/share CTA. NO hashtags in caption_ig.
- seo.keywords: 5-8 search phrases people type. seo.hashtags: 3-5 tightly relevant hashtags, each starting with #.
- seo.alt_text: one plain sentence describing the reel, containing the main keyword.
- seo.first_comment: a question that makes people reply.

{PSYCH}

RESEARCH NOTES:
RESEARCH_NOTES

TOPIC / BEAT SHEET: """


class Visual(BaseModel):
    type: Literal["none", "counter", "flow", "compare", "stamp", "list", "quote"]
    title: str = ""
    items: list[str] = []
    number: float = 0
    suffix: str = ""
    good: bool = True


class Line(BaseModel):
    text: str
    caption: str
    delivery: str
    footage: list[str]
    visual: Visual
    source: str


class Seo(BaseModel):
    keywords: list[str]
    hashtags: list[str]
    alt_text: str
    first_comment: str


class Reel(BaseModel):
    title: str
    genre: str
    hook: str
    music_mood: str
    caption_ig: str
    seo: Seo
    lines: list[Line]


def migrate(d):
    """Read scripts written by older versions (two hosts, typed visuals incl. hook/video/image/emoji)."""
    for l in d.get("lines", []):
        v = l.get("visual") or {}
        l.setdefault("footage", v.get("query", ""))
        if isinstance(l["footage"], str): l["footage"] = [l["footage"]]
        if v.get("type") not in Visual.model_fields["type"].annotation.__args__: l["visual"] = {"type": "none"}
        l.setdefault("delivery", ""); l.setdefault("source", "")
    d.setdefault("genre", ""); d.setdefault("music_mood", "calm background beat")
    d.setdefault("hook", next((l.get("visual", {}).get("title", "") for l in d.get("lines", [])[:1]), ""))
    d.setdefault("seo", {"keywords": [], "hashtags": [], "alt_text": "", "first_comment": ""})
    return Reel.model_validate(d)


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
                      json={"input": {"text": line.text}, "voice": {"languageCode": C["tts_language_code"], "name": f"{C['tts_language_code']}-Chirp3-HD-{C['voice']}"},
                            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}).json()
    if "audioContent" not in r: raise PermissionError(str(r.get("error", r))[:200])
    with wave.open(io.BytesIO(base64.b64decode(r["audioContent"]))) as w: save_wav(path, w.readframes(w.getnframes()))


CLOUD_TTS = E("TTS_ENGINE", "gemini") == "google"  # Chirp 3 HD voices have no emotion control; Gemini one-take is the default


def narrate(reel, path):
    """The whole script in ONE emotional take (natural flow between lines), directed like a real voice session."""
    script = "\n".join(f"[{l.delivery}] {l.text}" if l.delivery else l.text for l in reel.lines)
    prompt = f"""# AUDIO PROFILE: {C['voice_style']}.
## SCENE: Recording a {TARGET:.0f}-second Instagram reel, talking straight to one friend, not to an audience.
### DIRECTOR'S NOTES
Style: conversational, real emotion that changes line to line as marked in [brackets]; never say the brackets aloud.
Pacing: fast and lively, short natural pauses between lines, breathe naturally; slow down only where marked.
Accent: {C['accent']}.
#### TRANSCRIPT
{script}"""
    _, pcm = gemini(TTS_MODEL, [{"text": prompt}], responseModalities=["AUDIO"],
                    speechConfig={"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": C["voice"]}}})
    save_wav(path, pcm)


def pauses(path):
    """Real pauses in the audio (ffmpeg silencedetect) -> [(start, end)] seconds."""
    err = subprocess.run(["ffmpeg", "-i", str(path), "-af", "silencedetect=n=-35dB:d=0.18", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x.split("silence_start: ")[1].split()[0]) for x in err.splitlines() if "silence_start" in x]
    en = [float(x.split("silence_end: ")[1].split()[0]) for x in err.splitlines() if "silence_end" in x]
    return list(zip(st, en))


def split_take(reel, path):
    """Line start/end inside the one-take narration: estimate each boundary by text length, snap it to the nearest real pause."""
    with wave.open(str(path)) as w: total = w.getnframes() / w.getframerate()
    gaps = [g for g in pauses(path) if 0.05 < g[0] < total - 0.05]
    chars = [len(l.text) for l in reel.lines]; bounds, used = [], set()
    for k in range(1, len(chars)):
        est = total * sum(chars[:k]) / sum(chars)
        best = min((g for g in gaps if g not in used), key=lambda g: abs((g[0] + g[1]) / 2 - est), default=None)
        if best and abs((best[0] + best[1]) / 2 - est) < 1.5: used.add(best); bounds.append(best)
        else: bounds.append((est, est))
    bounds.sort()
    starts = [0.0] + [b[1] for b in bounds]; ends = [b[0] for b in bounds] + [total]
    return [(max(0.0, s - 0.02), e) for s, e in zip(starts, ends)]


def voice(line, path):
    """Google Cloud TTS (Chirp 3 HD) when enabled, else Gemini TTS (follows the acting note)."""
    global CLOUD_TTS
    if CLOUD_TTS:
        try: return google_tts(line, path)
        except PermissionError as e: CLOUD_TTS = False; print(f"  Google Cloud TTS unavailable ({str(e)[:90]}) -> Gemini TTS")
    return gemini_tts(line, path)


def gemini_tts(line, path):
    """Gemini TTS, one call per line with the narrator voice. Falls back to plainer prompts if one returns finishReason: OTHER."""
    voice_name = C["voice"]
    attempts = [
        f"Say in natural, quick, expressive Hindi: {line.text}",
        line.text,
        line.caption,
    ]
    last_err = None
    for text in attempts:
        try:
            _, pcm = gemini(LINE_TTS_MODEL, [{"text": text}],
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


LIB = Path("assets/coverr")  # local library: every Coverr clip ever downloaded (+ its metadata) and every search made
COVERR_DOWN = []


def coverr(query):
    """Coverr search, cached on disk (the demo key has a small query limit). One search per query, 20 results."""
    cache = LIB / "searches.json"; LIB.mkdir(parents=True, exist_ok=True)
    seen = json.loads(cache.read_text()) if cache.exists() else {}
    q = query.lower().strip()
    if q in seen: return seen[q]
    if COVERR_DOWN: return []
    r = requests.get("https://api.coverr.co/videos", timeout=30, headers={"Authorization": f"Bearer {E('COVERR_KEY')}"},
                     params={"query": q, "page_size": 20, "urls": "true"})
    if r.status_code != 200:
        COVERR_DOWN.append(r.status_code); print(f"  Coverr unavailable ({r.status_code}: {r.text[:60]}) -> using the local footage library")
        return []
    hits = [{k: h.get(k) for k in ("id", "title", "tags", "poster", "urls", "duration", "is_vertical")} for h in r.json().get("hits", [])]
    seen[q] = hits; cache.write_text(json.dumps(seen))
    return hits


def coverr_file(hit):
    """Download a Coverr 1080p clip once (cached by video id, with its metadata for the local library)."""
    f = LIB / f"{hit['id']}.mp4"
    if not f.exists():
        LIB.mkdir(parents=True, exist_ok=True)
        r = requests.get(hit["urls"]["mp4"], timeout=180)
        if r.status_code != 200 or not r.content[4:8] == b"ftyp": raise RuntimeError(f"Coverr download failed ({r.status_code})")
        f.write_bytes(r.content)
    if not f.with_suffix(".json").exists(): f.with_suffix(".json").write_text(json.dumps(hit))
    return f


def library_candidates(queries, used, k=8):
    """Already-downloaded Coverr clips ranked by word overlap with the line's searches."""
    words = set(re.findall(r"\w+", " ".join(queries).lower())); out = []
    for f in LIB.glob("*.mp4"):
        meta = json.loads(f.with_suffix(".json").read_text()) if f.with_suffix(".json").exists() else {"id": f.stem}
        if meta["id"] in used: continue
        text = set(re.findall(r"\w+", (str(meta.get("title", "")) + " " + " ".join(meta.get("tags") or [])).lower()))
        out.append((-len(words & text), meta))
    return [m for _, m in sorted(out, key=lambda x: x[0])[:k]]


def thumb(hit):
    """Small preview image of a candidate clip: Coverr's thumbnail, or a frame from a downloaded library clip."""
    f = LIB / f"{hit['id']}.thumb.jpg"
    if not f.exists():
        LIB.mkdir(parents=True, exist_ok=True)
        if (LIB / f"{hit['id']}.mp4").exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(LIB / f"{hit['id']}.mp4"), "-frames:v", "1",
                            "-vf", "scale=480:-1", str(f)], check=True)
        elif hit.get("thumbnail"): f.write_bytes(requests.get(hit["thumbnail"], timeout=30).content)
    return f.read_bytes() if f.exists() else None


def pick_footage(topic, say, queries, used):
    """Gemini looks at the candidate clips and picks the one that really shows what this line is about.
    Returns (hit, score 0-10, why). Nothing is generated - it only chooses among real Coverr clips."""
    cands = []
    for q in queries:
        for h in sorted(coverr(q), key=lambda h: not h.get("is_vertical")):
            if h["id"] not in used and all(h["id"] != c["id"] for c in cands): cands.append(h)
        if len(cands) >= 10: break
    cands = cands[:10] + library_candidates(queries, used | {c["id"] for c in cands}, 6)
    imgs = [(c, thumb(c)) for c in cands]; imgs = [(c, b) for c, b in imgs if b]
    if not imgs: return None, 0, "no candidates"
    parts = [{"text": f"You are the video editor of a news-explainer reel about: {topic}.\nThe narrator is saying: \"{say}\"\n"
                      f"Search intent: {queries[0]}.\nBelow are {len(imgs)} candidate stock clips (one preview frame each, numbered from 0). "
                      "Pick the ONE a good editor would put on screen under this line: it must clearly show the subject or a directly related "
                      "real-world scene (matching people, place or object). Generic filler or an unrelated scene must score low. "
                      'Reply JSON: {"best": index or -1, "score": 0-10, "why": "short"}'}]
    for k, (_, b) in enumerate(imgs): parts += [{"text": f"candidate {k}:"}, {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(b).decode()}}]
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=120,
                      json={"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}).json()
    j = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
    best = int(j.get("best", -1))
    return (imgs[best][0] if 0 <= best < len(imgs) else None), float(j.get("score", 0)), str(j.get("why", ""))[:120]


def stock_video(hit, path, secs):
    """Coverr clip -> full-screen 1080x1920, natural grade (no stylised look)."""
    start = min(1.0, float(hit.get("duration") or 4) / 5)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(coverr_file(hit)), "-t", f"{secs:.2f}",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.05:saturation=1.06,unsharp=5:5:0.35", "-an", "-r", "30",
                    "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", str(path.with_suffix(".tmp.mp4"))], check=True)
    path.with_suffix(".tmp.mp4").replace(path)


def grade(img, w, h):
    """cv2 natural grade: cover-crop, gentle local contrast, a touch of colour, soft vignette."""
    s = max(w / img.shape[1], h / img.shape[0])
    img = cv2.resize(img, (int(img.shape[1] * s) + 1, int(img.shape[0] * s) + 1), interpolation=cv2.INTER_CUBIC)
    y, x = (img.shape[0] - h) // 2, (img.shape[1] - w) // 2; img = img[y:y + h, x:x + w]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB); lab[..., 0] = cv2.createCLAHE(1.4, (8, 8)).apply(lab[..., 0])
    hsv = cv2.cvtColor(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.08, 0, 255)
    img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]; vig = 1 - 0.25 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    return img * vig[..., None]


def stock_image(hit, path, secs, seed=0):
    """Coverr still (the clip's poster frame) -> cv2 camera move: slow eased push-in + drift, light film grain.
    Used when a clip can't be downloaded, so a shot is never empty."""
    img = cv2.imdecode(np.frombuffer(requests.get(hit["poster"], timeout=60).content, np.uint8), cv2.IMREAD_COLOR)
    if img is None: raise RuntimeError("bad Coverr still")
    W, H, n = 1188, 2112, int(secs * 30) + 1
    base, rng, pan = grade(img, W, H), np.random.default_rng(seed), (-1) ** seed
    grain = rng.normal(0, 3.5, (1920 + 32, 1080 + 32, 1)).astype(np.float32)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1080x1920", "-r", "30",
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", str(path.with_suffix(".tmp.mp4"))], stdin=subprocess.PIPE)
    for f in range(n):
        e = 1 - (1 - f / max(n - 1, 1)) ** 2
        z = 1.1 * (1 + 0.08 * e); cw, ch = int(W / z), int(H / z)
        cx = int((W - cw) / 2 + pan * e * (W - cw) * 0.3); cy = int((H - ch) / 2)
        fr = cv2.resize(base[cy:cy + ch, cx:cx + cw], (1080, 1920), interpolation=cv2.INTER_LINEAR)
        oy, ox = rng.integers(0, 32, 2)
        ff.stdin.write(np.clip(fr + grain[oy:oy + 1920, ox:ox + 1080], 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode: raise RuntimeError("cv2 still render failed")
    path.with_suffix(".tmp.mp4").replace(path)


def valid_clip(f, min_secs=0.5):
    """A clip only counts as done if ffprobe can read a real video stream from it."""
    if not f.exists() or f.stat().st_size < 10000: return False
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip()) >= min_secs
    except ValueError: return False


def shots_for(lines, pub, topic):
    """Full-screen footage for every line that has a RELEVANT Coverr clip (judged by Gemini from preview frames);
    otherwise a bold text scene - never unrelated footage. A jump cut inside long lines, never the same clip twice.
    Decisions are saved in public/footage.json so a resume doesn't re-judge."""
    plan_f = pub / "footage.json"
    plan = json.loads(plan_f.read_text()) if plan_f.exists() else {}
    shots, used = [], {p["coverr_id"] for p in plan.values() if p.get("coverr_id")}
    for i, l in enumerate(lines):
        secs = l["end"] - l["start"] + 0.15
        f = pub / "clip" / f"{i}.mp4"
        say = " ".join(w for w, _ in l["words"])
        if str(i) not in plan or (plan[str(i)].get("coverr_id") and not valid_clip(f)):
            hit, score, why = None, 0, ""
            try: hit, score, why = pick_footage(topic, say, l["footage"], used)
            except Exception as e: why = f"judge failed: {e}"
            if hit and score >= FOOTAGE_MIN_SCORE:
                used.add(hit["id"])
                try:
                    stock_video(hit, f, secs + 4) if ((LIB / f"{hit['id']}.mp4").exists() or hit.get("urls")) else stock_image(hit, f, secs + 4, i)
                    plan[str(i)] = {"coverr_id": hit["id"], "title": hit.get("title", ""), "score": score, "why": why}
                except Exception as e: plan[str(i)] = {"coverr_id": None, "why": f"clip failed: {e}"}
            else: plan[str(i)] = {"coverr_id": None, "score": score, "why": why or "no relevant clip"}
            print(f"  line {i + 1}: " + (f"Coverr '{plan[str(i)].get('title')}' ({score:.0f}/10)" if plan[str(i)].get("coverr_id") else f"text scene ({plan[str(i)]['why']})"))
            plan_f.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
        if not plan[str(i)].get("coverr_id"):
            l["text_scene"] = True
            shots.append({"src": None, "start": l["start"], "end": round(l["end"] + 0.15, 2)}); continue
        cuts = [l["start"], round((l["start"] + l["end"]) / 2, 2)] if secs > 3.4 else [l["start"]]
        for k, c in enumerate(cuts):
            end = cuts[k + 1] if k + 1 < len(cuts) else l["end"] + 0.15
            shots.append({"src": f"clip/{i}.mp4", "start": round(c, 2), "end": round(end, 2), "offset": round((c - l["start"]) + 1.2 * k, 2)})
    return shots, plan


SFX = {  # synthesised once into assets/sfx - no downloads needed
    "pop": "aevalsrc='0.8*sin(2*PI*(400+2600*t)*t)*exp(-28*t)':d=0.15",
    "whoosh": "anoisesrc=d=0.45:c=pink:a=0.7,bandpass=f=1500:w=1400,afade=t=in:d=0.22,afade=t=out:st=0.22:d=0.23",
    "ding": "aevalsrc='0.5*sin(2*PI*1568*t)*exp(-5*t)+0.3*sin(2*PI*2349*t)*exp(-7*t)':d=0.9",
    "boom": "aevalsrc='0.9*sin(2*PI*(45+140*exp(-12*t))*t)*exp(-3.5*t)':d=0.8",
    "tick": "aevalsrc='0.6*sin(2*PI*2600*t)*exp(-90*t)':d=0.05",
}


def visual_times(v, t, dur):
    n = max(len(v["items"]), 1)
    return ([round(t + 0.1 + k * dur * 0.85 / n, 2) for k in range(n)] if v["type"] in ("flow", "list")
            else [round(t + 0.1, 2), round(t + dur * 0.45, 2)] if v["type"] == "compare" else [round(t + dur * 0.5, 2)])


def card_sfx(v, t, dur):
    return ([[x, "pop"] for x in v["times"]] * (v["type"] in ("flow", "list", "compare"))
            + [[v["times"][0], "ding" if v["good"] else "boom"]] * (v["type"] == "stamp")
            + [[round(t + k * 0.2, 2), "tick"] for k in range(int(dur * 0.6 / 0.2))] * (v["type"] == "counter"))


def word_times(caption, t, dur):
    words = caption.split(); wt = [len(x) + 3 for x in words]
    return [[x, round(t + dur * sum(wt[:k]) / sum(wt), 2)] for k, x in enumerate(words)]


def timeline_take(reel, d):
    """One-take narration -> voice.wav (sped up a little if over target), line timings from real pauses."""
    src = d / "narration.wav"
    with wave.open(str(src)) as w: total = w.getnframes() / w.getframerate()
    tempo = min(1.2, max(1.0, total / (TARGET - 1.8)))
    if tempo > 1.01:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={tempo:.3f}", "-ar", "24000", "-ac", "1",
                        str(d / "narration.fast.wav")], check=True); src = d / "narration.fast.wav"
    lines, sfx, lead = [], [[0.3, "boom"]], 0.3
    for l, (a, b) in zip(reel.lines, split_take(reel, src)):
        t, dur = lead + a, b - a
        v = l.visual.model_dump(); v["times"] = visual_times(v, t, dur); sfx += card_sfx(v, t, dur)
        lines.append({"start": round(t, 2), "end": round(t + dur, 2), "v": v, "source": l.source, "footage": l.footage,
                      "words": word_times(l.caption, t, dur)})
    with wave.open(str(src)) as w: pcm = w.readframes(w.getnframes())
    save_wav(d / "voice.wav", b"\0\0" * int(24000 * lead) + pcm)
    return lines, sfx, round(lines[-1]["end"] + 1.5, 2)


def timeline(reel, d):
    """Line-by-line fallback: concatenate line audio -> voice.wav; exact line timings, estimated word timings, SFX cues."""
    if (d / "narration.wav").exists(): return timeline_take(reel, d)
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
        sfx += [[x, "pop"] for x in v["times"]] * (v["type"] in ("flow", "list", "compare")) \
            + [[v["times"][0], "ding" if v["good"] else "boom"]] * (v["type"] == "stamp") \
            + [[round(t + k * 0.2, 2), "tick"] for k in range(int(dur * 0.6 / 0.2))] * (v["type"] == "counter")
        lines.append({"start": round(t, 2), "end": round(t + dur, 2), "v": v, "source": l.source, "footage": l.footage,
                      "words": [[x, round(t + dur * sum(wt[:k]) / sum(wt), 2)] for k, x in enumerate(words)]})
        pcm += data + b"\0\0" * int(24000 * 0.15); t += dur + 0.15
    save_wav(d / "voice.wav", b"\0\0" * 7200 + pcm)
    dur = round(t + 1.5, 2)
    return lines, sfx, dur


def make(brief, meta=None, d=None):
    """Script -> voice -> music + stock footage -> Remotion render. Pass d=<out dir> to resume a failed run."""
    with lock(): return _make(brief, meta, d)


def _make(brief, meta, d):
    d = Path(d) if d else OUT / time.strftime("%Y%m%d-%H%M%S"); pub = d / "public"
    for sub in ("img", "clip", "sfx"): (pub / sub).mkdir(parents=True, exist_ok=True)
    if (d / "script.json").exists():
        reel = migrate(json.loads((d / "script.json").read_text()))
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
    if not (d / "narration.wav").exists() and not (d / "line0.wav").exists() and not CLOUD_TTS:
        print(f"voice: one emotional take ({TTS_MODEL}, {C['voice']})...")
        try: retry(narrate, reel, d / "narration.wav", tries=3)
        except Exception as e: print(f"  one-take failed ({e}) -> line by line")
    if not (d / "narration.wav").exists():
        for i, l in enumerate(reel.lines):
            print(f"voice {i + 1}/{len(reel.lines)}: {l.caption}")
            if not (d / f"line{i}.wav").exists(): retry(voice, l, d / f"line{i}.wav")
    lines, sfx, dur = timeline(reel, d)
    shutil.copy(d / "voice.wav", pub / "voice.wav")
    shots, footage_plan = shots_for(lines, pub, reel.title)
    shots[-1]["end"] = dur  # last shot runs to the very end (no black tail)
    sfx += [[sh["start"], "whoosh"] for sh in shots[1:]]
    try: mus = (pub / "music.mp3").exists() and "music.mp3" or (pub / "music.wav").exists() and "music.wav" or music(reel.music_mood, pub)
    except Exception as e: print(f"  music skipped: {e}"); mus = ""
    Path("assets/sfx").mkdir(parents=True, exist_ok=True)
    for k, src in SFX.items():
        if not (f := Path(f"assets/sfx/{k}.wav")).exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, "-ar", "44100", "-ac", "1", str(f)], check=True)
        shutil.copy(f, pub / "sfx" / f"{k}.wav")
    print(f"  assets {time.time() - t0:.0f}s")
    props = {"duration": dur, "lines": lines, "shots": shots, "sfx": sfx, "voice": "voice.wav", "music": mus, "hook": reel.hook,
             "theme": C["theme"]}
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    t0 = time.time(); print(f"rendering {dur}s (Remotion)...")
    subprocess.run(["npx", "remotion", "render", "src/index.tsx", "Reel", str((d / "reel.mp4").resolve()), "--log=error",
                    f"--props={(d / 'props.json').resolve()}", f"--public-dir={pub.resolve()}", f"--concurrency={os.cpu_count()}"],
                   cwd="video", check=True)
    print(f"  render {time.time() - t0:.0f}s")
    tags = [h if h.startswith("#") else "#" + h for h in reel.seo.hashtags[:5]] + ([C["series_hashtag"]] if C["series_hashtag"] else [])
    caption = reel.caption_ig.strip() + "\n\n" + " ".join(dict.fromkeys(tags)) + ("\n🎥 Footage: coverr.co" if any(sh["src"] for sh in shots) else "")
    meta = {"title": reel.title, "genre": reel.genre, "brief": brief, "caption": caption, "posted": False, "status": "awaiting approval",
            "footage": [{"line": i + 1, "searches": l["footage"]} | footage_plan.get(str(i), {}) for i, l in enumerate(lines)],
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
    """One job at a time across processes (cron vs UI vs CLI). Use as `with lock():` - always released, even on errors.
    Re-entrant within a process."""
    def __enter__(self):
        self.f = None
        if _LOCK: return self
        self.f = open(".reel.lock", "w")
        try: fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: self.f.close(); raise RuntimeError("another reel job is running - try again when it finishes")
        _LOCK.append(self)
        return self

    def __exit__(self, *exc):
        if self.f: _LOCK.clear(); fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()


def auto():
    """Cron, approval-gated: posts the next episode ONLY if you approved that exact video in the UI.
    If the next episode isn't made yet, it is generated and left 'awaiting approval' - never posted silently."""
    with lock(): return _auto()


def _auto():
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
        gr.Markdown("# 🎬 AI Reels Studio\nGemini researches (Google Search) · Claude writes · Google voice · Lyria music · Coverr footage · Remotion edits · Buffer posts after your approval")
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
