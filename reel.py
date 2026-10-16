# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "python-dotenv", "opencv-python-headless", "numpy"]
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
import base64, contextlib, fcntl, hashlib, io, json, os, re, shutil, subprocess, sys, time, wave
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
     "voice": "Puck", "location": "India", "persona": "a fun, warm, patient teacher", "voice_style": "a popular creator in their late 20s - warm, quick-witted, genuinely excited",
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

BEAT = ("brief = a timed teaching beat sheet, one line per beat: HOOK (a moment from the viewer's own life), CONCEPT IN ONE "
        "SENTENCE, REAL-LIFE ANALOGY, HOW IT WORKS (2-4 steps, drawn on screen), LOCAL NEWS EXAMPLE (with source + date), "
        "MYTH vs TRUTH, YAAD RAKHO (one line to remember), SIGN-OFF; then 'EXAMPLE:', 'VISUALS:' (what is drawn/shown), "
        "'WHY NOW:'")

RESEARCH = f"""You are the researcher for a {TARGET:.0f}-second Instagram Reel. The reel is about EXACTLY what the USER PROMPT
(at the end) asks - whatever the subject is. ({CHANNEL}.)
Use Google Search. Be concise, bullet points, every fact with its date and source name. Sections:
0. UNDERSTANDING: in 2 lines, what the user wants - the topic, the angle, and the one takeaway the viewer should leave with.
1. LATEST NEWS: what happened in the last 60 days, {C['location']} first, that shows this concept in action - real,
   relatable examples a beginner would recognise (with source + date).
2. TRENDING: how this topic is trending - search interest, viral posts, memes, the angles other creators are using
   on Instagram / YouTube Shorts / X right now, and any hashtag or audio trend attached to it.
3. WHAT PEOPLE ARE SAYING: real questions, opinions, myths, complaints, jokes and slang from comments, Reddit, X,
   Quora, YouTube - quote short real phrasings where you can.
4. FACTS: 3-5 surprising, verified facts or numbers with source + date. Flag numbers that disagree between sources.
5. BEGINNER TEACHING: the concept in one plain sentence; 3 everyday analogies from {C['examples']} that make it click;
   the most common beginner confusion or myth and the truth; simple real data for a chart if any (years + values).
6. BEST EXAMPLES: list every candidate real-world example/story you found, score each 1-10 on: verified (named source,
   date), recent, relatable to a beginner in {C['location']}, and surprising. Mark the top 2 as KEEP and say why; mark the
   rest DROP. The script must only use KEEP examples.
7. SEO: 8 search phrases people actually type about this, 5 relevant hashtags in active use now, and current
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

BRIEF = f"""You are {C['persona']}.
You make a ~{TARGET:.0f}-second Instagram Reel that TEACHES exactly the concept in the user's prompt / beat sheet below to
{C['audience']}. Assume the viewer knows NOTHING - not even the basic words. After one watch they must be able to explain
the idea to someone else and remember one line by heart. Never switch to a different topic. ({CHANNEL}.)

FORMAT - "AI CASE FILE": every reel is a mystery case on a detective's corkboard. The hook opens the case with a
question; every line pins a new clue (footage polaroid, evidence card, animated character) and a red string connects it
to the last clue; the myth/truth line is a rubber stamp; the YAAD RAKHO line is the verdict "CASE SOLVED". Tell it like a
detective story - suspense, clues, reveal - while teaching. Give the case a short case_title (<= 4 words).
Also: one narrator (you, the teacher) over real stock footage that truly matches each line, plus simple animated
teaching visuals drawn on screen (definition card, step diagram, chart, comparison, myth/truth stamp, recap). No
presenters or characters on camera. It must feel like a real, warm creator - nothing that looks AI-generated.

VIRAL PLAYBOOK (from analysing 13 Shorts with 10M-38M views - Zack D. Films, Mrwhosetheboss, Cleo Abram, Dhruv Rathee,
AI Warehouse - see research/competitors_10M.json). Follow it:
- First second: a spoken AND visual hook together, no intro. Use a counter-intuitive claim, a common mistake, a myth
  attack or a "what if" image ("Agar duniya ki saari kitaabein ek computer ko padha di jaayein...?"). Never a generic
  "Kabhi socha hai AI kaise kaam karta hai?".
- Start from an everyday thing the viewer has seen a hundred times, then reveal the hidden "how" inside it.
- Carry ONE strong visual metaphor through the whole reel so the invisible becomes visible.
- Keep a result pending (a test, a showdown, "Hour 1 vs Hour 100", a countdown) so they must watch to the end.
- Escalate the reveals ("pehle ye... lekin asli kamaal ye hai...") with a tiny pause before each one.
- Proof on screen: real numbers with sources, real-world examples, side-by-side before/after.
- Personal stakes in Indian terms: money (₹), job, time, safety, family.
- PACE: slow and clear (about 2 spoken words per second) but EXCITING: every line either builds suspense or pays it
  off. Use story tension - "Ruko...", "Aur yahan twist hai...", "Socho zara...", "Ab dhyaan se suno..." - a dramatic pause
  before each reveal, then a big "aha" payoff. Mini-cliffhangers between lines so the viewer can't scroll away.
  Emotional contrast line to line (whisper -> excited, serious -> laughing). Never flat, never rushed, zero filler.
- End with a clear payoff or verdict whose last words echo the hook (so the loop replays), or a debate question.
- Give a reason to send it ("us dost ko bhejo jo...").

TEACHING ARC (in this order, one idea per line, 9-12 short lines, total spoken words about {int(TARGET * 2.0)}):
1. HOOK - a specific moment from the viewer's own life (or today's news) where they already met this concept, plus the
   promise: e.g. "Aapka phone aapki photo mein chehra kaise pehchaanta hai? 40 second mein samjho."
2. CONCEPT - say what it is in ONE simple sentence, zero jargon. Show a define card: TERM = meaning in 3-6 everyday words.
3. ANALOGY - an everyday analogy from {C['examples']} that makes it click. Footage of that real-life scene.
4. HOW IT WORKS - 2-4 tiny steps, drawn on screen (diagram or flow). Each step = one simple action.
5. REAL EXAMPLE - a real, recent news example from {C['location']} (from the research, with source + date) showing it in action.
6. TRUTH CHECK - one common myth or fear about it, and the honest truth (stamp card). Be 100% truthful; no hype, no scare.
7. YAAD RAKHO - one short, catchy line to remember by heart (rhythm or rhyme helps). Show it on the recap card.
8. SIGN-OFF - warm and fun, and its last words echo the hook so the reel loops; tease the next lesson if given, else a
   save/share invite.
Any technical word must be explained the moment it appears. Speak like a fun teacher: warm, soft, a little playful, smiling.

FIELDS
- text: what you say, in {C['spoken_language']}. caption: the SAME words in {C['caption_language']}.
- Timing: a flow/diagram/list needs about 1.2 seconds per item, so give that line enough words; keep the whole reel
  close to {TARGET:.0f} seconds (never above {TARGET + 10:.0f}).
- emoji: 1-2 emoji that act out this line as ANIMATED characters/objects (e.g. "🤖", "🧠💡", "📚", "🤔", "🚀", "💸").
  Pick only from this animated set: ANIM_SET
- onscreen: the line's key idea in 2-5 words (shown big when the line has no footage or card) - never the full sentence.
- delivery: the emotion for this line, 1-5 words, BIG and varied like a great storyteller: "suspense, whispering",
  "gasp, shocked", "slow build, then excited", "laughing", "big excited reveal", "dramatic pause, then serious",
  "proud, punchy", "teasing, playful". Never repeat the same delivery twice in a row.
- hook: <= 6 words shown big during line 1 - the concept's name + the curious part.
- footage: 3 STOCK VIDEO search options (2-3 English words each), most specific first, then broader, then a simpler
  scene that still clearly relates - e.g. ["woman shopping vegetables", "vegetable market", "market"]. Describe what a
  camera would see (people, places, objects). Relatable everyday scenes. A different scene every line.
- visual: the teaching visual for this line - type "none" when the footage alone teaches it; otherwise:
  define  - title = the term, items = [the meaning in 3-6 everyday words]
  diagram - title + items = 2-4 nodes left-to-right with an emoji each, e.g. ["📩 Message", "🧮 Words gino", "🚫 Spam"]
  flow    - title + items = 2-4 steps top-to-bottom
  chart   - title + items = 3-6 labels + values = numbers (same count) + chart: "line" or "bar" + suffix; only real
            numbers from the research, labels like years
  counter - number + suffix + title for a QUANTITY (only real numbers from the research, and the SAME number must be in the
            spoken text). Never for phone numbers, helplines, years or codes - put those in a quote or list card.
  compare - title + items [left, right]
  stamp   - title (the myth or the truth in <= 6 words) + good (true = TRUTH ✅, false = MYTH ❌)
  list    - title + 2-3 items
  chat    - title = app name (e.g. "ChatGPT") + items = [what a person types, the AI's short reply] - a phone demo that
            SHOWS the concept in action (great for anything you can ask an AI). Keep both under 12 words.
  recap   - title = the YAAD RAKHO line
  define / diagram / flow / chart / chat / recap are drawn on a bright whiteboard (no footage) - use AT MOST 4 of these.
  counter / stamp / compare / list / quote float as stickers OVER real footage - so still give good footage searches.
  "none" = just real footage + captions. Alternate real footage and whiteboard so it never feels like slides.
  Always use define (line 2), one diagram/flow/chart or chat (how it works), and recap.
  Line 1 (hook) is always type "none" so it opens on real footage.
- The channel's fixed signature line is inserted automatically right after your hook - do not write any intro or
  channel greeting yourself; go straight from the hook into the concept.
  On-screen text: max 6 words per item, in {C['caption_language']}.
- source: for a news fact or number, "Publication · date" from the research notes (max 35 characters, e.g. "PIB · Aug 2026"), else "".
- music_mood: light background music (e.g. "soft playful ukulele", "warm curious lo-fi").
- Use the RESEARCH NOTES for every fact, number and the news example; never invent numbers or events.
- Numbers the Indian way, so beginners feel them: lakh/crore, never million/billion (22.9 billion -> "2,290 crore"),
  rounded and said simply ("lagbhag 2,300 crore"), and the same number + unit on the card as in the spoken line.

SEO (Instagram reads captions, on-screen text and the spoken audio):
- Pick ONE main search keyword (usually the concept's name). Say it in line 1 or 2, put it in the hook, and start caption_ig with it.
- caption_ig: line 1 = "<concept> kya hai? <one-line answer>" style hook, under 125 characters; then the YAAD RAKHO line and
  2 short lines of value with 2-3 more search phrases; end with a save/share CTA. NO hashtags in caption_ig.
- seo.keywords: 5-8 search phrases people type. seo.hashtags: 3-5 tightly relevant hashtags, each starting with #.
- seo.alt_text: one plain sentence describing the reel, containing the main keyword.
- seo.first_comment: a fun, genuine question that makes people reply with what they learned or a doubt (no engagement bait).
- seo.story_text: one line to reshare the reel on Stories (curiosity, not a summary).
- seo.broadcast_text: one friendly line for the broadcast channel announcing today's lesson.

{PSYCH}

RESEARCH NOTES:
RESEARCH_NOTES

TOPIC / BEAT SHEET: """


class Visual(BaseModel):
    type: Literal["none", "define", "diagram", "flow", "chart", "counter", "compare", "stamp", "list", "recap", "quote", "chat", "brand"]
    title: str = ""
    items: list[str] = []
    number: float = 0
    suffix: str = ""
    good: bool = True
    values: list[float] = []
    chart: Literal["line", "bar"] = "bar"


class Line(BaseModel):
    text: str
    caption: str
    onscreen: str
    emoji: str
    delivery: str
    footage: list[str]
    visual: Visual
    source: str


class Seo(BaseModel):
    keywords: list[str]
    hashtags: list[str]
    alt_text: str
    first_comment: str
    story_text: str = ""
    broadcast_text: str = ""


class Reel(BaseModel):
    title: str
    genre: str
    case_title: str
    hook: str
    music_mood: str
    caption_ig: str
    seo: Seo
    lines: list[Line]


def add_signature(reel):
    """Insert the channel's constant signature line (config.json -> signature) right after the hook."""
    sg = C.get("signature") or {}
    if not sg.get("text") or any(l.visual.type == "brand" for l in reel.lines): return reel
    reel.lines.insert(1, Line(text=sg["text"], caption=sg.get("caption", sg["text"]), onscreen=sg.get("title", ""), delivery=sg.get("delivery", ""), emoji=sg.get("emoji", "☕"),
                              footage=[], source="", visual=Visual(type="brand", title=sg.get("title", ""), items=[sg.get("subtitle", "")], suffix=sg.get("emoji", ""))))
    return reel


def write_checked(prompt, tries=3):
    """Write a script, then repair mechanical problems (length, numbers, missing beats) up to `tries` times."""
    reel = add_signature(retry(ask, prompt, Reel, tries=2))
    for n in range(tries):
        if not (issues := check_script(reel)): break
        print(f"  fixing ({n + 1}/{tries}):", "; ".join(issues))
        reel = add_signature(retry(ask, prompt + "\n\nYOUR PREVIOUS DRAFT HAD THESE PROBLEMS - fix every one (cut whole lines if it is too long; "
                                   "keep the hook, define, how-it-works and recap):\n- " + "\n- ".join(issues)
                                   + "\nPREVIOUS DRAFT:\n" + reel.model_dump_json(), Reel, tries=2))
    return reel


def check_script(reel):
    """Mechanical checks before paying for voice/footage: card numbers must be spoken, charts complete, teaching beats present."""
    issues, types = [], [l.visual.type for l in reel.lines]
    for i, l in enumerate(reel.lines, 1):
        v, spoken = l.visual, re.sub(r"[,\s]", "", l.text + l.caption)
        if v.type == "counter" and not re.search(rf"(?<!\d){re.escape(f'{v.number:g}')}(?!\d)", spoken):
            issues.append(f"line {i}: the card shows {v.number:g}{v.suffix} but the narrator does not say that number")
        if v.type == "chart" and (len(v.values) != len(v.items) or len(v.items) < 3):
            issues.append(f"line {i}: chart needs 3-6 labels and the same number of values")
        if v.type in ("define", "diagram", "flow", "list", "compare") and not v.items:
            issues.append(f"line {i}: {v.type} card has no items")
    for need, why in (("define", "a define card for the concept"), ("recap", "a recap (YAAD RAKHO) card")):
        if need not in types: issues.append(f"missing {why}")
    if not set(types) & {"diagram", "flow", "chart", "chat"}: issues.append("missing a diagram/flow/chart/chat showing how it works")
    words = sum(len(l.text.split()) for l in reel.lines if l.visual.type != "brand"); cap = int(TARGET * 2.1)
    if words > cap: issues.append(f"too long: {words} spoken words - cut to at most {cap} (about {TARGET:.0f} seconds at a slow, clear pace)")
    return issues


def migrate(d):
    """Read scripts written by older versions (two hosts, typed visuals incl. hook/video/image/emoji)."""
    for l in d.get("lines", []):
        v = l.get("visual") or {}
        l.setdefault("footage", v.get("query", ""))
        if isinstance(l["footage"], str): l["footage"] = [l["footage"]]
        if v.get("type") not in Visual.model_fields["type"].annotation.__args__: l["visual"] = {"type": "none"}
        l.setdefault("delivery", ""); l.setdefault("source", "")
        l.setdefault("onscreen", " ".join(l.get("caption", "").split()[:4])); l.setdefault("emoji", "")
    d.setdefault("genre", ""); d.setdefault("music_mood", "calm background beat"); d.setdefault("case_title", d.get("hook", "")[:30])
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


# ---------- usage + cost ledger (Gemini paid-tier prices, USD per 1M tokens, from ai.google.dev/gemini-api/docs/pricing) ----------
PRICES = {"gemini-3.8-flash": (0.75, 3.75), "gemini-2.5-pro-preview-tts": (1.00, 20.00), "gemini-2.5-flash-preview-tts": (0.50, 10.00),
          "gemini-2.5-flash": (0.30, 2.50)}
GROUNDING_USD, LYRIA_USD = 0.014, 0.04  # per grounded request (after 5,000 free/month), per 30s Lyria clip
USAGE: list = []


def track(step, model, r=None, extra_usd=0.0, note=""):
    """Record one AI call: real token counts from the API response and what it costs."""
    u = (r or {}).get("usageMetadata", {}) if isinstance(r, dict) else {}
    tin, tout = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
    pin, pout = PRICES.get(model, (0, 0))
    USAGE.append({"step": step, "model": model, "in": tin, "out": tout, "usd": round(tin * pin / 1e6 + tout * pout / 1e6 + extra_usd, 5), "note": note})


def usage_summary():
    steps = {}
    for u in USAGE:
        g = steps.setdefault(u["step"], {"calls": 0, "in": 0, "out": 0, "usd": 0.0, "model": u["model"]})
        g["calls"] += 1; g["in"] += u["in"]; g["out"] += u["out"]; g["usd"] = round(g["usd"] + u["usd"], 5)
    gem = round(sum(u["usd"] for u in USAGE if not u["model"].startswith("claude")), 4)
    cl = round(sum(u["usd"] for u in USAGE if u["model"].startswith("claude")), 4)
    return {"gemini_usd": gem, "claude_usd_equivalent": cl, "calls": len(USAGE), "steps": steps}


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
    track("script (Gemini fallback)", "gemini-2.5-flash", r)
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
        j = json.loads(out); u = j.get("usage", {})
        USAGE.append({"step": "script (Claude)" if schema is Reel else f"{schema.__name__.lower()} (Claude)", "model": "claude",
                      "in": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
                      "out": u.get("output_tokens", 0), "usd": round(j.get("total_cost_usd", 0), 5), "note": "covered by your Claude subscription"})
        return schema.model_validate(j["structured_output"])
    except Exception:
        CLAUDE_AVAILABLE = False
        print("⚡ Claude session limit reached. Automatically switching to Gemini 2.5 Flash fallback.")
        return ask_gemini(prompt, schema)


def save_wav(path, pcm, rate=24000):
    with wave.open(str(path), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def gemini(model, parts, step="media", **config):
    """Gemini API (REST) -> (mime, bytes) of the first media part."""
    r = requests.post(f"{GEMINI}/{model}:generateContent", headers=GKEY(), timeout=300,
                      json={"contents": [{"parts": parts}], "generationConfig": config}).json()
    track(step, model, r, LYRIA_USD if model.startswith("lyria") else 0.0)
    for p in ((r.get("candidates") or [{}])[0].get("content") or {}).get("parts", []):
        if "inlineData" in p: return p["inlineData"]["mimeType"], base64.b64decode(p["inlineData"]["data"])
    raise RuntimeError(f"{model}: {str(r.get('error') or r)[:300]}")


def research(topic, extra=""):
    """Gemini + Google Search grounding -> concise research notes with sources (news, facts, analogies, SEO)."""
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=300,
                      json={"contents": [{"parts": [{"text": RESEARCH + extra + "\nTOPIC: " + topic}]}], "tools": [{"google_search": {}}]}).json()
    track("research (Google Search)", RESEARCH_MODEL, r, GROUNDING_USD, "grounding free for the first 5,000/month")
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


VOICE_JUDGE = ("You are a strict voice director for Indian Instagram creators. Listen to this take. Reply JSON: "
               '{"brackets_or_directions_read_aloud": true/false, "sounds_like_real_teacher": 1-10, "emotion_range": 1-10, '
               '"warmth": 1-10, "excitement": 1-10 (dynamic range, suspense, energy - 1 = monotone), "not_rushed": 1-10, '
               '"pronunciation": 1-10, "worst_moment": "..."}')


VOICES = C.get("voices") or ["Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr", "Achird", "Sulafat",
                              "Sadachbia", "Algieba", "Iapetus", "Umbriel", "Laomedeia", "Gacrux", "Vindemiatrix", "Schedar", "Alnilam", "Rasalgethi"]


def pick_voices(k=2):
    """Different voices every reel: skip the voices used in the last few reels, then pick k at random."""
    import random
    recent = []
    for f in sorted(OUT.glob("*/meta.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:6]:
        try: recent.append(json.loads(f.read_text()).get("voice"))
        except Exception: pass
    pool = [v for v in VOICES if v not in recent] or VOICES
    return random.sample(pool, min(k, len(pool)))


def narrate_take(reel, path, n=0, voice=None):
    """One emotional take of the whole script, directed like a real teacher's voice session."""
    script = "\n".join(f"[{l.delivery}] {l.text}" if l.delivery else l.text for l in reel.lines)
    prompt = f"""# AUDIO PROFILE: {C['voice_style']}. Everyone's favourite teacher - the one who makes hard things feel easy.
## SCENE: Sitting next to one curious student, explaining something cool with a big smile. Recording an Instagram
reel, but talking to ONE person, never to an audience. Take {n + 1}.
### DIRECTOR'S NOTES
Style: a real teacher, not an announcer. Smile while speaking - you can hear it. Change emotion line to line exactly as
marked in [brackets]; never say the brackets aloud.
PACE: slow, clear and deliberate - never rushed - but bursting with energy. Huge dynamic range: drop to a near-whisper
for suspense, then explode with excitement on the reveal. A real dramatic pause (about one second) before every reveal
and after every question, as if waiting for the student. Lean hard on key words. Real gasps, real laughs where marked.
Teaching moments: slow and warm, then a bright "samjhe?!" feel. "Yaad rakho" line: slow, punchy, proud.
Think of a thrilling storyteller telling kids a mystery: suspense -> surprise -> joy. Never flat, never monotone.
Accent: {C['accent']}.
#### TRANSCRIPT
{script}"""
    _, pcm = gemini(TTS_MODEL, [{"text": prompt}], step="voice takes", responseModalities=["AUDIO"],
                    speechConfig={"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice or C["voice"]}}})
    save_wav(path, pcm)


def judge_voice(path):
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=300, json={"contents": [{"parts": [
        {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(Path(path).read_bytes()).decode()}}, {"text": VOICE_JUDGE}]}],
        "generationConfig": {"responseMimeType": "application/json"}}).json()
    track("voice judge", RESEARCH_MODEL, r)
    j = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
    j["score"] = -99 if j.get("brackets_or_directions_read_aloud") else sum(j.get(k, 0) for k in ("sounds_like_real_teacher", "emotion_range", "warmth", "pronunciation", "not_rushed")) + 2 * j.get("excitement", 0)
    return j


def narrate(reel, path):
    """VOICE_TAKES takes (default 2), each with a DIFFERENT voice; Gemini listens and the most human-sounding one is kept."""
    takes, voices = [], pick_voices(int(E("VOICE_TAKES", "2")))
    for n, v in enumerate(voices):
        f = path.with_name(f"take{n}.wav")
        try:
            retry(narrate_take, reel, f, n, v, tries=2)
            j = judge_voice(f) | {"voice": v}; takes.append((j["score"], f, j)); print(f"  take {n + 1} ({v}): teacher {j.get('sounds_like_real_teacher')}/10, emotion {j.get('emotion_range')}/10, excitement {j.get('excitement')}/10")
        except Exception as e: print(f"  take {n + 1} failed: {e}")
    if not takes: raise RuntimeError("no voice take succeeded")
    best = max(takes, key=lambda x: x[0]); shutil.copy(best[1], path); path.with_name("voice.txt").write_text(best[2]["voice"])
    path.with_name("voice_takes.json").write_text(json.dumps([{"take": f.name, **j} for _, f, j in takes], ensure_ascii=False, indent=1))


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
            _, pcm = gemini(LINE_TTS_MODEL, [{"text": text}], step="voice (line by line)",
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
    mime, data = gemini(MUSIC_MODEL, step="music (Lyria)", parts=[{"text": f"30-second instrumental background track for an exciting but slow-paced explainer reel: {mood}. "
                                                "About 85-95 BPM, cinematic and playful: light percussion, plucks, a curious mystery feel that keeps "
                                                "building tension with small lifts. No vocals, loopable."}])
    name = "music.wav" if "wav" in mime else "music.mp3"
    (d / name).write_bytes(data)
    return name


def _anim_catalogue():
    """Google Noto Animated Emoji (Apache-2.0 Lottie): emoji character -> codepoint, skin-tone variants skipped."""
    f = Path("assets/lottie/api.json")
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(requests.get("https://googlefonts.github.io/noto-emoji-animation/data/api.json", timeout=30).text)
    out = {}
    for x in json.loads(f.read_text())["icons"]:
        cp = x["codepoint"]
        if any(t in cp for t in ("1f3fb", "1f3fc", "1f3fd", "1f3fe", "1f3ff")): continue
        out["".join(chr(int(h, 16)) for h in cp.split("_"))] = cp
    return out


try: ANIM = _anim_catalogue()
except Exception: ANIM = {}
BRIEF = BRIEF.replace("ANIM_SET", " ".join(e for e in ANIM if len(e) <= 2) or "any emoji")


def anim_cps(emoji):
    """Map the writer's emoji string to available animated-emoji codepoints (max 2)."""
    out, rest = [], emoji or ""
    for ch in sorted(ANIM, key=len, reverse=True):
        if ch in rest: out.append(ANIM[ch]); rest = rest.replace(ch, " ")
        if len(out) == 2: break
    if not out:
        stripped = rest.replace("\ufe0f", "")
        out = [ANIM[c] for c in stripped if c in ANIM][:2]
    return out


def lottie(cp):
    f = Path("assets/lottie") / f"{cp}.json"
    if not f.exists():
        r = requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{cp}/lottie.json", timeout=30)
        if r.status_code != 200: return None
        f.write_text(r.text)
    return json.loads(f.read_text())


LIB = Path("assets/coverr")  # local library: every Coverr clip ever downloaded (+ its metadata) and every search made
COVERR_DOWN = []


def coverr(query):
    """Coverr search, cached on disk (the demo key has a small query limit). One search per query, 20 results."""
    q = query.lower().strip()
    if (hit := cache_get(q)) is not None: return hit
    if COVERR_DOWN: return []
    r = requests.get("https://api.coverr.co/videos", timeout=30, headers={"Authorization": f"Bearer {E('COVERR_KEY')}"},
                     params={"query": q, "page_size": 20, "urls": "true"})
    if r.status_code != 200:
        with _CACHE_LOCK:
            if not COVERR_DOWN: COVERR_DOWN.append(r.status_code); print(f"  Coverr unavailable ({r.status_code}: {r.text[:60]}) - using other sources")
        return []
    hits = [{k: h.get(k) for k in ("id", "title", "tags", "poster", "urls", "duration", "is_vertical")} for h in r.json().get("hits", [])]
    cache_put(q, hits)
    return hits


def pexels(query):
    """Pexels free stock video (needs PEXELS_KEY), cached like Coverr; mapped to the same clip format."""
    if not E("PEXELS_KEY"): return []
    key = "px:" + query.lower().strip()
    if (hit := cache_get(key)) is not None: return hit
    r = requests.get("https://api.pexels.com/videos/search", timeout=30, headers={"Authorization": E("PEXELS_KEY")},
                     params={"query": query, "per_page": 15, "orientation": "portrait", "size": "medium"})
    if r.status_code != 200: print(f"  Pexels unavailable ({r.status_code})"); return []
    hits = []
    for v in r.json().get("videos", []):
        files = sorted([f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 1280],
                       key=lambda f: abs((f.get("height") or 0) - 1920))
        if files: hits.append({"id": f"px{v['id']}", "title": v.get("url", "").rstrip("/").split("/")[-1].replace("-", " "), "tags": [],
                               "poster": v.get("image"), "thumbnail": v.get("image"), "urls": {"mp4": files[0]["link"]},
                               "duration": v.get("duration"), "is_vertical": v.get("height", 0) > v.get("width", 1), "source": "pexels",
                               "credit": (v.get("user") or {}).get("name", "")})
    cache_put(key, hits)
    return hits


import threading
_CACHE_LOCK = threading.Lock()


def cache_get(key):
    with _CACHE_LOCK:
        f = LIB / "searches.json"
        if not f.exists(): return None
        try: return json.loads(f.read_text()).get(key)
        except ValueError: return None


def cache_put(key, value):
    """Thread-safe, atomic write (parallel footage judging used to corrupt the file)."""
    with _CACHE_LOCK:
        f = LIB / "searches.json"; LIB.mkdir(parents=True, exist_ok=True)
        try: seen = json.loads(f.read_text()) if f.exists() else {}
        except ValueError: seen = {}
        seen[key] = value; tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(seen)); tmp.replace(f)


SOURCE_DOWN: set = set()
_POLITE = {"wm": threading.Lock(), "ia": threading.Lock()}
NAMES = {"ov": "Openverse", "wm": "Wikimedia Commons", "ia": "Internet Archive", "pb": "Pixabay", "px": "Pexels"}


def cached(key, fetch):
    """Disk cache for every footage search (keeps free-tier API limits for new queries).
    A source that fails once is skipped for the rest of this run."""
    if (hit := cache_get(key)) is not None: return hit
    src = key.split(":")[0]
    if src in SOURCE_DOWN: return []
    try:
        with (_POLITE[src] if src in _POLITE else contextlib.nullcontext()):  # Wikimedia/Archive rate-limit bursts
            try: value = fetch()
            except Exception: time.sleep(2); value = fetch()
    except Exception as e:
        with _CACHE_LOCK:
            if src not in SOURCE_DOWN: SOURCE_DOWN.add(src); print(f"  {NAMES.get(src, src)} unavailable ({str(e)[:60]}) - skipping it this run")
        return []
    cache_put(key, value); return value


UA = {"User-Agent": "auto-social/1.0 (educational reels; contact via repo owner)"}
FREE_LICENSES = ("cc0", "public domain", "pd", "pdm")


def openverse(query):
    """Openverse: CC0 / public-domain photos (no key). Shown as a cv2 camera move over the still."""
    def go():
        r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=30,
                         params={"q": query, "license": "cc0,pdm", "page_size": 12, "size": "large"}).json()
        return [{"id": f"ov{x['id']}", "title": x.get("title", ""), "tags": [t["name"] for t in (x.get("tags") or [])][:10],
                 "poster": x["url"], "thumbnail": x.get("thumbnail") or x["url"], "urls": None, "source": "openverse"}
                for x in r.get("results", []) if (x.get("width") or 0) >= 800]
    return cached("ov:" + query.lower().strip(), go)


def commons(query):
    """Wikimedia Commons videos, CC0 / public-domain only (no credit needed), under 120 MB (no key)."""
    def go():
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:video {query}", "gsrnamespace": 6,
            "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 480}).json()
        out = []
        for pg in r.get("query", {}).get("pages", {}).values():
            ii = pg["imageinfo"][0]; lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "").lower()
            if any(lic.startswith(f) for f in FREE_LICENSES) and ii.get("size", 1e12) < 120e6:
                out.append({"id": f"wm{pg['pageid']}", "title": pg["title"].removeprefix("File:").rsplit(".", 1)[0], "tags": [],
                            "poster": ii.get("thumburl"), "thumbnail": ii.get("thumburl"), "urls": {"mp4": ii["url"]}, "source": "commons"})
        return out
    return cached("wm:" + query.lower().strip(), go)


def prelinger(query):
    """Internet Archive's Prelinger collection: curated public-domain films - great for history (no key)."""
    def go():
        r = requests.get("https://archive.org/advancedsearch.php", headers=UA, timeout=30, params={
            "q": f"({query}) AND collection:prelinger AND mediatype:movies", "fl[]": ["identifier", "title"], "rows": 8, "output": "json"}).json()
        return [{"id": f"ia{x['identifier']}", "title": x.get("title", ""), "tags": [], "thumbnail": f"https://archive.org/services/img/{x['identifier']}",
                 "poster": f"https://archive.org/services/img/{x['identifier']}", "urls": {"mp4": f"archive:{x['identifier']}"}, "source": "prelinger"}
                for x in r.get("response", {}).get("docs", [])]
    return cached("ia:" + query.lower().strip(), go)


def pixabay(query):
    """Pixabay free videos (needs PIXABAY_KEY)."""
    if not E("PIXABAY_KEY"): return []
    def go():
        r = requests.get("https://pixabay.com/api/videos/", timeout=30, params={"key": E("PIXABAY_KEY"), "q": query, "per_page": 15, "safesearch": "true"}).json()
        out = []
        for v in r.get("hits", []):
            vs = v.get("videos") or {}
            f = next((vs[k] for k in ("medium", "large", "small") if (vs.get(k) or {}).get("url")), {})  # 1080p first; large can be empty
            if f.get("url"): out.append({"id": f"pb{v['id']}", "title": v.get("tags", ""), "tags": v.get("tags", "").split(", "),
                                         "poster": f.get("thumbnail"), "thumbnail": f.get("thumbnail"), "urls": {"mp4": f["url"]},
                                         "duration": v.get("duration"), "is_vertical": f.get("height", 0) > f.get("width", 1), "source": "pixabay"})
        return out
    return cached("pb:" + query.lower().strip(), go)


def all_sources(query):
    """Video sources first, then public-domain stills; capped per source so judging stays fast."""
    return coverr(query)[:6] + pexels(query)[:6] + pixabay(query)[:5] + commons(query)[:4] + prelinger(query)[:3]  # moving video only


def coverr_file(hit):
    """Download a Coverr 1080p clip once (cached by video id, with its metadata for the local library)."""
    f = LIB / f"{hit['id']}.mp4"
    if not f.exists():
        LIB.mkdir(parents=True, exist_ok=True)
        url = hit["urls"]["mp4"]
        if url.startswith("archive:"):  # pick the smallest MPEG4 derivative of the Archive item
            ident = url.split(":", 1)[1]; files = requests.get(f"https://archive.org/metadata/{ident}", headers=UA, timeout=30).json().get("files", [])
            mp4 = sorted((x for x in files if x.get("name", "").endswith(".mp4")), key=lambda x: int(x.get("size", 1e12)))
            if not mp4 or int(mp4[0].get("size", 1e12)) > 80e6: raise RuntimeError("no small mp4 in Archive item")
            url = f"https://archive.org/download/{ident}/{mp4[0]['name']}"
        r = requests.get(url, headers=UA, timeout=300)
        if r.status_code != 200 or not (r.content[4:8] == b"ftyp" or r.content[:4] in (b"\x1aE\xdf\xa3", b"OggS") or r.content[:3] == b"\x00\x00\x01"):
            raise RuntimeError(f"footage download failed ({r.status_code})")
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
        elif hit.get("thumbnail"):
            try:
                img = cv2.imdecode(np.frombuffer(requests.get(hit["thumbnail"], headers=UA, timeout=30).content, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    s_ = 480 / max(img.shape[:2]); cv2.imwrite(str(f), cv2.resize(img, None, fx=min(1, s_), fy=min(1, s_)), [cv2.IMWRITE_JPEG_QUALITY, 85])
            except Exception: pass
    return f.read_bytes() if f.exists() and f.stat().st_size > 1000 else None


def pick_footage(topic, say, queries, used):
    """Gemini looks at preview frames of real candidate clips/photos and ranks the ones that really show what this
    line is about. Returns [(hit, score 0-10, why), ...] best first (up to 3). Nothing is generated."""
    import concurrent.futures as cf
    cands = []
    for q in queries:
        for h in sorted(all_sources(q), key=lambda h: not h.get("is_vertical")):
            if h["id"] not in used and all(h["id"] != c["id"] for c in cands): cands.append(h)
        if len(cands) >= 16: break
    cands = cands[:16] + library_candidates(queries, used | {c["id"] for c in cands}, 4)
    with cf.ThreadPoolExecutor(8) as ex: thumbs = list(ex.map(thumb, cands))
    imgs = [(c, b) for c, b in zip(cands, thumbs) if b]
    if not imgs: return []
    parts = [{"text": f"You are the video editor of an explainer reel about: {topic}.\nThe narrator is saying: \"{say}\"\n"
                      f"Search intent: {queries[0]}.\nBelow are {len(imgs)} candidate stock clips/photos (one preview frame each, numbered from 0). "
                      "Rank the ones a good editor would put on screen under this line: they must clearly show the subject or a directly related "
                      "real-world scene (matching people, place or object). Generic filler or an unrelated scene must score low. "
                      'Reply JSON: {"ranked": [{"index": i, "score": 0-10, "why": "short"}] (best first, max 3), "best_reason_if_none": "..."}'}]
    for k, (_, b) in enumerate(imgs): parts += [{"text": f"candidate {k}:"}, {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(b).decode()}}]
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=180,
                      json={"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}).json()
    track("footage judge", RESEARCH_MODEL, r, note=f"{len(imgs)} preview images")
    if not r.get("candidates"): raise RuntimeError(f"footage judge: {str(r.get('error') or r)[:200]}")
    j = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
    out = [(imgs[x["index"]][0], float(x.get("score", 0)), str(x.get("why", ""))[:120]) for x in j.get("ranked", [])
           if isinstance(x.get("index"), int) and 0 <= x["index"] < len(imgs)]
    return out or [(None, 0.0, str(j.get("best_reason_if_none", "no relevant clip"))[:120])]


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
    img = cv2.imdecode(np.frombuffer(requests.get(hit["poster"], headers=UA, timeout=60).content, np.uint8), cv2.IMREAD_COLOR)
    if img is None: raise RuntimeError("still image could not be downloaded")
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


BOARD = ("define", "diagram", "flow", "chart", "chat", "recap", "brand")  # drawn on the whiteboard; other cards float over footage


def shots_for(lines, pub, topic):
    """Full-screen footage for every line that has a RELEVANT real clip/photo (judged by Gemini from preview frames);
    otherwise a key-idea text scene - never unrelated footage. All lines are judged in parallel, then clips are assigned
    in order (never the same clip twice), falling back to the next-ranked candidate if a download fails.
    Decisions are saved in public/footage.json so a resume doesn't re-judge."""
    import concurrent.futures as cf
    plan_f = pub / "footage.json"
    plan = json.loads(plan_f.read_text()) if plan_f.exists() else {}
    need = [i for i, l in enumerate(lines) if l["v"]["type"] not in BOARD
            and (str(i) not in plan or (plan[str(i)].get("coverr_id") and not valid_clip(pub / "clip" / f"{i}.mp4")))]
    taken = {p["coverr_id"] for k, p in plan.items() if p.get("coverr_id") and int(k) not in need}

    def judge(i):
        try: return i, retry(pick_footage, topic, " ".join(w for w, _ in lines[i]["words"]), lines[i]["footage"], taken, tries=3)
        except Exception as e: return i, [(None, 0.0, f"judge failed: {e}")]
    with cf.ThreadPoolExecutor(4) as ex: ranked = dict(ex.map(judge, need))
    used = set(taken)
    for i in need:  # assign in order: no clip twice, next-ranked candidate if a download fails
        l, f = lines[i], pub / "clip" / f"{i}.mp4"; secs = l["end"] - l["start"] + 0.15
        plan[str(i)] = {"coverr_id": None, "why": (ranked[i][0][2] if ranked[i] else "no candidates") or "no relevant clip",
                        "score": ranked[i][0][1] if ranked[i] else 0}
        for hit, score, why in ranked[i]:
            if not hit or score < FOOTAGE_MIN_SCORE or hit["id"] in used: continue
            try:
                if not ((LIB / f"{hit['id']}.mp4").exists() or hit.get("urls")): continue  # no stills - real motion only
                stock_video(hit, f, secs + 4)
                if not valid_clip(f): raise RuntimeError("clip did not render")
                used.add(hit["id"]); plan[str(i)] = {"coverr_id": hit["id"], "title": hit.get("title", ""), "score": score, "why": why,
                                                     "source": hit.get("source", "coverr"), "credit": hit.get("credit", "")}
                break
            except Exception as e: plan[str(i)]["why"] = f"download failed ({e})"
        p_ = plan[str(i)]
        print(f"  line {i + 1}: " + (f"{p_['source']} '{p_['title'][:50]}' ({p_['score']:.0f}/10)" if p_.get("coverr_id") else f"text scene ({p_['why'][:100]})"))
    for i, l in enumerate(lines):
        if l["v"]["type"] in BOARD: plan[str(i)] = {"coverr_id": None, "why": "whiteboard teaching visual"}
    plan_f.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    for i, l in enumerate(lines):  # case-file polaroids: the clip + a still of it for when the camera has moved on
        if plan[str(i)].get("coverr_id"):
            l["clip"], l["still"] = f"clip/{i}.mp4", f"clip/{i}.jpg"
            if not (pub / "clip" / f"{i}.jpg").exists():
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(pub / "clip" / f"{i}.mp4"), "-frames:v", "1",
                                "-vf", "scale=720:-1", str(pub / "clip" / f"{i}.jpg")], check=False)
    shots = []
    for i, l in enumerate(lines):
        secs = l["end"] - l["start"] + 0.15
        if not plan[str(i)].get("coverr_id"):
            l["text_scene"] = l["v"]["type"] not in BOARD
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
    "riser": "anoisesrc=d=0.9:c=white:a=0.5,highpass=f=800,volume='0.15+0.85*t/0.9':eval=frame,afade=t=in:d=0.6,afade=t=out:st=0.85:d=0.05",
    "impact": "aevalsrc='0.95*sin(2*PI*(38+90*exp(-9*t))*t)*exp(-2.8*t)+0.25*(random(0)-0.5)*exp(-14*t)':d=1.0",
    "sparkle": "aevalsrc='0.25*(sin(2*PI*2093*t)*exp(-6*t)+sin(2*PI*2637*(t-0.08))*exp(-6*(t-0.08))*gt(t,0.08)+sin(2*PI*3136*(t-0.16))*exp(-6*(t-0.16))*gt(t,0.16))':d=0.9",
}


SEQ = ("flow", "list", "diagram", "chart")  # cards whose items appear one by one, spread over the line


def visual_times(v, t, dur):
    n = max(len(v["items"]), 1)
    return ([round(t + 0.15 + k * dur * 0.8 / n, 2) for k in range(n)] if v["type"] in SEQ
            else [round(t + 0.1, 2), round(t + dur * 0.45, 2)] if v["type"] in ("compare", "chat")
            else [round(t + min(0.6, dur * 0.25), 2)] if v["type"] in ("define", "recap", "brand") else [round(t + dur * 0.5, 2)])


def card_sfx(v, t, dur):
    hit = v["times"][0] if v.get("times") else t
    return ([[max(0.0, round(hit - 0.85, 2)), "riser"], [hit, "impact"]] * (v["type"] in ("define", "stamp", "counter", "compare", "chart", "recap"))
            + [[round(hit + 0.2, 2), "sparkle"]] * (v["type"] in ("recap", "define", "brand")) + ([[x, "pop"] for x in v["times"]] * (v["type"] in SEQ + ("compare", "define"))
            + [[v["times"][0], "ding"]] * (v["type"] in ("recap", "brand"))
            + [[v["times"][0], "ding" if v["good"] else "boom"]] * (v["type"] == "stamp")
            + [[round(t + k * 0.2, 2), "tick"] for k in range(int(dur * 0.6 / 0.2))] * (v["type"] == "counter")))


def word_times(caption, t, dur):
    words = caption.split(); wt = [len(x) + 3 for x in words]
    return [[x, round(t + dur * sum(wt[:k]) / sum(wt), 2)] for k, x in enumerate(words)]


def timeline_take(reel, d):
    """One-take narration -> voice.wav (sped up a little if over target), line timings from real pauses."""
    src = d / "narration.wav"
    with wave.open(str(src)) as w: total = w.getnframes() / w.getframerate()
    tempo = 1.0  # never speed the voice up - slow, clear pace
    if tempo > 1.01:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={tempo:.3f}", "-ar", "24000", "-ac", "1",
                        str(d / "narration.fast.wav")], check=True); src = d / "narration.fast.wav"
    lines, sfx, lead = [], [[0.3, "boom"]], 0.3
    for l, (a, b) in zip(reel.lines, split_take(reel, src)):
        t, dur = lead + a, b - a
        v = l.visual.model_dump(); v["times"] = visual_times(v, t, dur); sfx += card_sfx(v, t, dur)
        lines.append({"start": round(t, 2), "end": round(t + dur, 2), "v": v, "source": l.source, "footage": l.footage,
                      "onscreen": l.onscreen, "words": word_times(l.caption, t, dur), "anim": anim_cps(l.emoji)})
    with wave.open(str(src)) as w: pcm = w.readframes(w.getnframes())
    save_wav(d / "voice.wav", b"\0\0" * int(24000 * lead) + pcm)
    return lines, sfx, round(lines[-1]["end"] + 1.5, 2)


def timeline(reel, d):
    """Line-by-line fallback: concatenate line audio -> voice.wav; exact line timings, estimated word timings, SFX cues."""
    if (d / "narration.wav").exists(): return timeline_take(reel, d)
    t, pcm, lines, sfx = 0.3, b"", [], [[0.3, "boom"]]
    talk = sum(wave.open(str(d / f"line{i}.wav")).getnframes() for i in range(len(reel.lines))) / 24000
    tempo = 1.0  # never speed the voice up - slow, clear pace
    for i, l in enumerate(reel.lines):
        src = d / f"line{i}.wav"
        if tempo > 1.01:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"atempo={tempo:.3f}", "-ar", "24000", "-ac", "1",
                            str(d / f"line{i}.fast.wav")], check=True); src = d / f"line{i}.fast.wav"
        with wave.open(str(src)) as w: data = w.readframes(w.getnframes())
        dur, words = len(data) / 48000, l.caption.split()
        wt = [len(x) + 3 for x in words]
        v, n = l.visual.model_dump(), max(len(l.visual.items), 1)
        v["times"] = visual_times(v, t, dur)
        sfx += [[x, "pop"] for x in v["times"]] * (v["type"] in ("flow", "list", "compare")) \
            + [[v["times"][0], "ding" if v["good"] else "boom"]] * (v["type"] == "stamp") \
            + [[round(t + k * 0.2, 2), "tick"] for k in range(int(dur * 0.6 / 0.2))] * (v["type"] == "counter")
        lines.append({"start": round(t, 2), "end": round(t + dur, 2), "v": v, "source": l.source, "footage": l.footage,
                      "onscreen": l.onscreen, "words": [[x, round(t + dur * sum(wt[:k]) / sum(wt), 2)] for k, x in enumerate(words)], "anim": anim_cps(l.emoji)})
        pcm += data + b"\0\0" * int(24000 * 0.15); t += dur + 0.15
    save_wav(d / "voice.wav", b"\0\0" * 7200 + pcm)
    dur = round(t + 1.5, 2)
    return lines, sfx, dur


REVIEW = f"""Today's date is TODAY (dates up to today are real, not typos). You are a complete beginner: {C['audience']}. You know NOTHING about tech. Watch this whole reel carefully
(picture AND sound), exactly as you would on Instagram. Then answer honestly as JSON:
- learned: in one simple sentence, explain the concept back in your own words (if you can't, say so)
- remember: the one line you'd remember tomorrow
- scores 1-10: hook (would you stop scrolling?), clarity (did you understand it?), teaching (could you explain it to a friend?),
  fun, visual_match (do the visuals show what is being said at that moment?), looks_real (feels like a real creator, not AI),
  pacing, accuracy (anything that sounds false, exaggerated or confusing?)
- problems: list of {{"time": "m:ss", "issue": "...", "fix": "a concrete change to the script or visuals"}} - be strict
- verdict: "post" if you'd watch to the end and share it, else "fix"
The concept being taught: CONCEPT. The script lines: SCRIPT"""


MARKETING_CHECKLIST = """## Before posting
- [ ] Watch it once with sound and once muted (captions must carry it).
- [ ] Cover: upload `cover.jpg` (title sits in the centre, safe for the 3:4 / 1:1 grid crop).
- [ ] Caption: paste the caption above; first line has the keyword.
- [ ] Advanced settings: paste the alt text. Keep 3-5 hashtags (they organise, they don't add reach).
- [ ] New hook style? Post it as a **Trial Reel** first (shown to non-followers only), share to followers if it performs.

## Best time (India, IST)
- Tue/Wed 7:00-9:30 PM best; weekdays 12-2 PM next; weekends 11 AM-1 PM or 8-10 PM.
- Then check Professional Dashboard > Insights > Most active times and follow your own audience.

## First hour after posting
- [ ] Post the first comment above and pin it.
- [ ] Reply to every real comment in the first hour (conversations count).
- [ ] Reshare to Stories with the story line; drop the broadcast line in your channel.
- [ ] Send it to 3-5 people who genuinely care about the topic - sends per reach is the #1 signal for non-follower reach.

## Growth habits
- Profile Name field (searchable) should contain your main keyword, e.g. "AI Seekho | Hindi".
- Collab posts with other educators share one view/comment pool across both audiences.
- Never repost with another app's watermark; keep every reel original and 1080p.
"""


def marketing(d, reel, caption):
    """A ready-to-use marketing pack per reel: caption, alt text, comments, story/broadcast lines, cover, timing, checklist."""
    s = reel.seo
    md = (f"# {reel.title}\n\n## Caption\n```\n{caption}\n```\n\n## Alt text\n{s.alt_text}\n\n"
          f"## First comment (pin it)\n{s.first_comment}\n\n## Story reshare line\n{s.story_text}\n\n"
          f"## Broadcast channel\n{s.broadcast_text}\n\n## Search keywords used\n" + ", ".join(s.keywords) + "\n\n" + MARKETING_CHECKLIST)
    (d / "marketing.md").write_text(md, encoding="utf-8")
    return md


def review(d, reel):
    """Gemini watches the finished reel as a beginner viewer: what it learned, scores, timestamped problems."""
    small = d / "review.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(d / "reel.mp4"), "-vf", "scale=360:-2", "-r", "15", "-c:v", "libx264",
                    "-crf", "32", "-c:a", "aac", "-b:a", "64k", str(small)], check=True)
    prompt = (REVIEW.replace("CONCEPT", reel.title).replace("SCRIPT", " | ".join(l.caption for l in reel.lines))
              .replace("TODAY", time.strftime("%d %b %Y")))
    video = base64.b64encode(small.read_bytes()).decode()

    def one(_):
        r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=600, json={"contents": [{"parts": [
            {"inlineData": {"mimeType": "video/mp4", "data": video}}, {"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}).json()
        track("beginner review", RESEARCH_MODEL, r)
        return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(2) as ex: runs = [x for x in ex.map(lambda k: (lambda: one(k))(), range(2))]  # two independent viewers
    small.unlink()
    j = runs[0] | {"scores": {k: round(sum(r.get("scores", {}).get(k, 0) for r in runs) / len(runs), 1) for k in runs[0].get("scores", {})},
                   "problems": [p for r in runs for p in r.get("problems", [])],
                   "verdict": "post" if all(r.get("verdict") == "post" for r in runs) else "fix"}
    (d / "review.json").write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    sc = j.get("scores", {})
    print(f"  review: {j.get('verdict')} | " + " ".join(f"{k} {v}" for k, v in sc.items()) + f"\n  learned: {j.get('learned')}")
    return j


def total(j):
    return sum(v for k, v in (j or {}).get("scores", {}).items() if k != "fun") + (j or {}).get("scores", {}).get("fun", 0) * 0.5


def needs_fix(j):
    sc = j.get("scores", {})
    return j.get("verdict") != "post" or min(sc.get(k, 10) for k in ("hook", "clarity", "teaching", "visual_match", "accuracy")) < 7


def make(brief, meta=None, d=None):
    """Script -> voice -> music + stock footage -> Remotion render. Pass d=<out dir> to resume a failed run."""
    with lock():
        USAGE.clear(); t0 = time.time()
        out = _make(brief, meta, d)
        u = usage_summary() | {"minutes": round((time.time() - t0) / 60, 1), "detail": list(USAGE)}
        rd = Path(out[0]).parent; (rd / "usage.json").write_text(json.dumps(u, ensure_ascii=False, indent=1))
        print(f"  usage: Gemini ${u['gemini_usd']:.3f} · Claude ≈${u['claude_usd_equivalent']:.2f} (subscription) · {u['calls']} AI calls · {u['minutes']} min")
        return out


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
        try: notes = retry(research, brief[:1500], tries=3)
        except Exception as e: notes = "(research unavailable)"; print(f"  research skipped: {e}")
        (d / "research.txt").write_text(notes, encoding="utf-8"); print(f"  {time.time() - t0:.0f}s")
        t0 = time.time(); print("writing (Claude)..."); prompt = BRIEF.replace("RESEARCH_NOTES", notes) + brief
        reel = write_checked(prompt)
        (d / "script.json").write_text(reel.model_dump_json(indent=2), encoding="utf-8"); print(f"  {time.time() - t0:.0f}s")
    print(f"  {reel.title} | {reel.genre}")
    t0 = time.time()
    if not (d / "narration.wav").exists() and not (d / "line0.wav").exists() and not CLOUD_TTS:
        print(f"voice: one emotional take ({TTS_MODEL}, trying different voices)...")
        try: narrate(reel, d / "narration.wav")
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
    anims = {cp: data for cp in {c for l in lines for c in l.get("anim", [])} if (data := lottie(cp))}
    for l in lines: l["anim"] = [c for c in l.get("anim", []) if c in anims]
    if (spark := lottie("2728")): anims["2728"] = spark  # sparkle burst on reveals
    for l in lines:  # a pop each time an animated character jumps in
        if l.get("anim") and (l.get("text_scene") or l["v"]["type"] in BOARD):
            sfx += [[round(l["start"] + 0.3 + q * 0.4, 2), "pop"] for q in range(len(l["anim"]))]
    props = {"lottie": anims, "duration": dur, "lines": lines, "shots": shots, "sfx": sfx, "voice": "voice.wav", "music": mus, "hook": reel.hook, "case_title": reel.case_title,
             "case_no": (meta or {}).get("ep") or len(list(OUT.glob("*/meta.json"))) + 1, "theme": C["theme"], "captions": bool(C.get("captions", False))}
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    t0 = time.time(); print(f"rendering {dur}s (Remotion)...")
    subprocess.run(["npx", "remotion", "render", "src/index.tsx", "Reel", str((d / "reel.mp4").resolve()), "--log=error",
                    f"--props={(d / 'props.json').resolve()}", f"--public-dir={pub.resolve()}", f"--concurrency={os.cpu_count()}"],
                   cwd="video", check=True)
    print(f"  render {time.time() - t0:.0f}s")
    try:
        (d / "cover_props.json").write_text(json.dumps(props | {"cover": True}, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["npx", "remotion", "still", "src/index.tsx", "Reel", str((d / "cover.jpg").resolve()), "--frame=0", "--log=error",
                        f"--props={(d / 'cover_props.json').resolve()}", f"--public-dir={pub.resolve()}"], cwd="video", check=True)
    except Exception as e: print(f"  cover skipped: {e}")
    tags = [h if h.startswith("#") else "#" + h for h in reel.seo.hashtags[:5]] + ([C["series_hashtag"]] if C["series_hashtag"] else [])
    caption = reel.caption_ig.strip() + "\n\n" + " ".join(dict.fromkeys(tags))
    meta = {"title": reel.title, "genre": reel.genre, "brief": brief, "caption": caption, "posted": False, "status": "awaiting approval",
            "voice": (d / "voice.txt").read_text() if (d / "voice.txt").exists() else C["voice"],
            "footage": [{"line": i + 1, "searches": l["footage"]} | footage_plan.get(str(i), {}) for i, l in enumerate(lines)],
            "first_comment": reel.seo.first_comment, "keywords": reel.seo.keywords, "alt_text": reel.seo.alt_text} | (meta or {})
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    marketing(d, reel, caption)
    try: rv = review(d, reel)
    except Exception as e: rv = None; print(f"  review skipped: {e}")
    job = json.loads((d / "job.json").read_text()) if (d / "job.json").exists() else {}
    if rv and needs_fix(rv) and not job.get("revised") and int(E("REVIEW_FIXES", "1")):
        print("  revising the script from the review and re-rendering once...")
        fix = "\n".join(f"- {p.get('time', '')}: {p.get('issue', '')} -> {p.get('fix', '')}" for p in rv.get("problems", []))
        notes = (d / "research.txt").read_text() if (d / "research.txt").exists() else ""
        new = write_checked(BRIEF.replace("RESEARCH_NOTES", notes) + brief + "\n\nA BEGINNER WATCHED YOUR LAST VERSION. They learned: "
                            f"{rv.get('learned')}. Scores: {rv.get('scores')}. Fix every problem below, keep what worked:\n{fix}\n"
                            "LAST VERSION:\n" + reel.model_dump_json())
        v1 = d / "v1"; v1.mkdir(exist_ok=True)  # keep the first version; restored if the revision scores lower
        for f in [d / "reel.mp4", d / "cover.jpg", d / "meta.json", d / "marketing.md", d / "props.json"]:
            if f.exists(): shutil.copy(f, v1 / f.name)
        for f in [*d.glob("line*.wav"), *d.glob("narration*.wav"), *d.glob("take*.wav"), d / "voice.wav", d / "props.json", pub / "footage.json", *(pub / "clip").glob("*.mp4")]:
            f.unlink(missing_ok=True)
        (d / "script.v1.json").write_text((d / "script.json").read_text()); (d / "review.v1.json").write_text((d / "review.json").read_text())
        (d / "script.json").write_text(new.model_dump_json(indent=2), encoding="utf-8")
        (d / "job.json").write_text(json.dumps(job | {"revised": True}))
        return _make(brief, meta, d)
    if rv and job.get("revised") and (d / "review.v1.json").exists() and (d / "v1" / "reel.mp4").exists():
        old = json.loads((d / "review.v1.json").read_text())
        if total(old) > total(rv):  # the revision came out worse: put version 1 back
            print(f"  revision scored lower ({total(rv):.0f} < {total(old):.0f}) -> keeping version 1")
            for f in (d / "v1").iterdir(): shutil.copy(f, d / f.name)
            (d / "script.json").write_text((d / "script.v1.json").read_text()); rv = old
            caption = json.loads((d / "meta.json").read_text())["caption"]
    if rv: meta = json.loads((d / "meta.json").read_text()) | {"review": {k: rv.get(k) for k in ("verdict", "scores", "learned", "remember")}}; (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
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
    if m.exists() and json.loads(m.read_text()).get("first_comment") and E("BUFFER_FIRST_COMMENT", "1") == "1":
        ig["firstComment"] = json.loads(m.read_text())["first_comment"]
    url, note = upload(video), ""  # upload once, even if the post has to be retried

    def create(meta_ig):
        try:
            r = buffer("""mutation($input: CreatePostInput!) { createPost(input: $input) {
                ... on PostActionSuccess { post { id } } ... on MutationError { message } } }""", input={
                "text": caption, "channelId": E("BUFFER_CHANNEL_ID"), "schedulingType": "automatic",
                "mode": E("BUFFER_MODE", "addToQueue"),
                "assets": [{"video": {"url": url, "metadata": {"thumbnailOffset": 1333}}}],
                "metadata": {"instagram": meta_ig}})["createPost"]
        except RuntimeError as e: r = {"message": str(e).removeprefix("Buffer: ")}
        return r
    p = create(ig)
    if "post" not in p and "first comment" in str(p.get("message", "")).lower() and "firstComment" in ig:
        # Buffer's free plan can't post first comments: post without it, the comment is in marketing.md to add by hand
        ig.pop("firstComment"); p = create(ig)
        note = "\n\n💬 Buffer's free plan can't add the first comment - post it yourself from the SEO & marketing pack and pin it."
    if "post" not in p:
        if m.exists(): set_status(video, status="failed", error=str(p.get("message", p))[:300])
        raise RuntimeError(f"Buffer: {p.get('message', p)}")
    if m.exists():  # remember it in history / series
        j = set_status(video, posted=True, status="queued", fingerprint=fp, buffer_post_id=p["post"]["id"],
                       caption=caption, posted_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        if j.get("series"):
            sr = load(j["series"]); sr["episodes"][j["ep"] - 1]["status"] = "posted"; save(sr)
    return f"✅ Sent to Buffer ({E('BUFFER_MODE', 'addToQueue')}) - post id {p['post']['id']}" + note


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


def write_episode_script(sr, i, notes):
    """Full script for one episode, written up front so you can read all of them before making any video."""
    eps, e = sr["episodes"], sr["episodes"][i]
    nxt = f"\nNEXT EPISODE (tease it at the end): {eps[i + 1]['title']}" if i + 1 < len(eps) else "\nThis is the series finale."
    prev = f"\nPREVIOUS CASE: #{i} {eps[i - 1]['title']} - open with a one-line callback to it." if i else ""
    brief = f"Series '{sr['name']}', CASE #{i + 1}/{len(eps)}: {e['title']} ({e['era']})\n{e['brief']}{prev}{nxt}"
    return write_checked(BRIEF.replace("RESEARCH_NOTES", notes) + brief).model_dump()


def plan_series(subject, n=10):
    """Plan the playlist AND write every episode's script now. Videos are made later, one Run at a time."""
    import concurrent.futures as cf
    USAGE.clear()
    print("researching the whole story (Gemini + Google Search)...")
    notes = retry(research, subject, "8. Key milestones from the origins to today and what is coming next: year, who, what changed, "
                              f"why it mattered - enough for {int(n)} daily episodes.\n")
    print("planning episodes (Claude)...")
    sr = ask(PLAN_SERIES.replace("N_EPISODES", str(int(n))) + "\nRESEARCH NOTES:\n" + notes + "\n\n" + subject, Series)
    sr = {"id": slug(sr.name), "name": sr.name, "subject": subject, "notes": notes, "created": time.strftime("%Y-%m-%d %H:%M"),
          "episodes": [e.model_dump() | {"status": "planned"} for e in sr.episodes]}
    save(sr)
    print(f"writing {len(sr['episodes'])} scripts...")

    def one(i):
        try: sr["episodes"][i].update(script=write_episode_script(sr, i, notes), status="scripted"); print(f"  script {i + 1} ready: {sr['episodes'][i]['title']}")
        except Exception as ex: print(f"  script {i + 1} failed: {ex}")
        save(sr)
    with cf.ThreadPoolExecutor(3) as ex: list(ex.map(one, range(len(sr["episodes"]))))
    sr = load(sr["id"]); sr["planning_usage"] = usage_summary(); save(sr)
    print(f"  usage: Gemini ${sr['planning_usage']['gemini_usd']:.3f} · Claude ≈${sr['planning_usage']['claude_usd_equivalent']:.2f} (subscription)")
    return sr


def episode_context(sr, i):
    """What the previous episode taught us: its script, what the beginner viewers learned, scores and problems."""
    if i == 0: return ""
    p = sr["episodes"][i - 1]
    out = f"\nPREVIOUS CASE #{i}: {p['title']}."
    if p.get("video") and (Path(p["video"]).parent / "review.json").exists():
        rv = json.loads((Path(p["video"]).parent / "review.json").read_text())
        out += (f"\nViewers of the previous video learned: {rv.get('learned')}. Scores: {rv.get('scores')}."
                "\nProblems they saw (do NOT repeat these):\n" + "\n".join(f"- {x.get('issue')} -> {x.get('fix')}" for x in rv.get("problems", [])[:8]))
    if p.get("script"):
        recap = next((l["visual"]["title"] for l in p["script"]["lines"] if l["visual"]["type"] == "recap"), "")
        out += f"\nPrevious YAAD RAKHO line: \"{recap}\" - open with a one-line callback to it, then go straight into this case."
    return out


def make_episode(sr, i):
    """Make one episode's video: fresh research today, the pre-written script refined with it, continuity from the last video."""
    eps, e = sr["episodes"], sr["episodes"][i]
    nxt = f"\nNEXT EPISODE (tease it): {eps[i + 1]['title']}" if i + 1 < len(eps) else "\nThis is the series finale."
    draft = ("\n\nDRAFT SCRIPT written earlier for this episode - keep its story and structure, but update facts and examples "
             "with today's research (KEEP examples only) and apply the lessons from the previous video:\n" + json.dumps(e["script"], ensure_ascii=False)) if e.get("script") else ""
    video, cap = make(f"Series '{sr['name']}', CASE #{i + 1}/{len(eps)}: {e['title']} ({e['era']})\n{e['brief']}{nxt}{episode_context(sr, i)}{draft}",
                      {"title": f"#{i + 1} {e['title']}", "series": sr["id"], "ep": i + 1})
    sr = load(sr["id"]); sr["episodes"][i].update(status="generated", video=video); save(sr)
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
    if e["status"] in ("planned", "scripted"):
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


def stream(fn, *a):
    """Run a long job in a thread and yield its printed progress live (for the UI)."""
    import contextlib, io, queue, threading
    q, out = queue.Queue(), {}

    class W(io.TextIOBase):
        def write(self, x): q.put(x); return len(x)

    def run():
        try:
            with contextlib.redirect_stdout(W()): out["result"] = fn(*a)
        except Exception as e: out["error"] = f"{type(e).__name__}: {e}"
        q.put(None)
    threading.Thread(target=run, daemon=True).start()
    log = ""
    while (x := q.get()) is not None:
        log += x; yield log[-6000:], None
    yield log[-6000:], out


def outputs(video):
    """Everything the UI shows for a finished reel."""
    d = Path(video).parent; m = json.loads((d / "meta.json").read_text())
    rv = m.get("review") or {}; sc = rv.get("scores") or {}
    rmd = (f"### Beginner review: **{rv.get('verdict', '-')}**\n" + " · ".join(f"{k} **{v}**" for k, v in sc.items())
           + f"\n\n> They learned: {rv.get('learned', '')}\n\n> They'll remember: {rv.get('remember', '')}") if rv else ""
    mk = (d / "marketing.md").read_text() if (d / "marketing.md").exists() else ""
    return str(d / "reel.mp4"), m["caption"], mk, rmd, str(d / "cover.jpg") if (d / "cover.jpg").exists() else None, str(d / "reel.mp4")


def ui():
    import gradio as gr

    def ep_rows(sid):
        return [[i + 1, e["era"], e["title"], e["status"]] for i, e in enumerate(load(sid)["episodes"])] if sid else []

    def series_ids():
        return [(load(f.stem)["name"], f.stem) for f in sorted(SERIES.glob("*.json"))]

    def safe_post(path, cap):  # clicking Post = explicit approval of this exact video + caption
        if not path: return "❌ Make or pick a reel first"
        try: approve(path, cap); return post(path, cap)
        except Exception as e: return f"❌ {type(e).__name__}: {e}"

    def safe_approve(path, cap):
        if not path: return "❌ Pick a reel first"
        try: return approve(path, cap) + " - the scheduled job may now post it"
        except Exception as e: return f"❌ {type(e).__name__}: {e}"

    def run_single(prompt):
        if not prompt.strip(): raise gr.Error("Type what the reel should teach first")
        for log, out in stream(make, prompt.strip()):
            if out is None: yield log, None, "", "", "", None, None; continue
            if "error" in out: yield log + f"\n❌ {out['error']}", None, "", "", "", None, None; return
            yield (log + "\n✅ Ready - review it, then post.", *outputs(out["result"][0]))

    def run_playlist(subject, n, now, sid):
        log = ""
        if not sid:
            if not subject.strip(): raise gr.Error("Type the playlist subject, or pick an existing playlist")
            for log, out in stream(plan_series, subject.strip(), n):
                yield log, gr.update(), [], None, "", "", "", None, None
            if "error" in out: yield log + f"\n❌ {out['error']}", gr.update(), [], None, "", "", "", None, None; return
            sid = out["result"]["id"]; log += f"\n📚 Planned '{out['result']['name']}' - {len(out['result']['episodes'])} episodes\n"
        sr, last = load(sid), None
        todo = [i for i, e in enumerate(sr["episodes"]) if e["status"] == "planned"][:int(now)]
        for k, i in enumerate(todo):
            head = log + f"\n🎬 {k + 1}/{len(todo)} - episode {i + 1}: {sr['episodes'][i]['title']}\n"
            for l2, out in stream(make_episode, sr, i):
                yield head + l2, gr.update(choices=series_ids(), value=sid), ep_rows(sid), *(outputs(last) if last else (None, "", "", "", None, None))
            if "error" in out: yield head + f"\n❌ {out['error']}", gr.update(), ep_rows(sid), *(outputs(last) if last else (None, "", "", "", None, None)); return
            last, log = out["result"][0], head + "✅ done\n"; sr = load(sid)
        yield log + ("\n✅ Ready - review each episode in History, then post." if todo else "\nNothing left to make in this playlist."), \
            gr.update(choices=series_ids(), value=sid), ep_rows(sid), *(outputs(last) if last else (None, "", "", "", None, None))

    def pick_ep(sid, evt: gr.SelectData):
        e = load(sid)["episodes"][evt.index[0]]
        return f"### #{evt.index[0] + 1} {e['title']} · {e['era']} · {e['status']}\n```\n{e['brief']}\n```"

    def pick_run(evt: gr.SelectData):
        return outputs(OUT / history()[evt.index[0]][0] / "reel.mp4")

    def result_panel():
        vid = gr.Video(label="Reel", height=600)
        cover = gr.Image(label="Cover (upload as the reel cover)", height=300)
        cap = gr.Textbox(label="Caption (editable)", lines=6)
        with gr.Row():
            appr = gr.Button("✅ Approve for scheduled post")
            pst = gr.Button("📤 Post now via Buffer", variant="primary")
        status = gr.Markdown()
        rv = gr.Markdown()
        with gr.Accordion("📈 SEO & marketing pack", open=False): mk = gr.Markdown()
        path = gr.State()
        appr.click(safe_approve, [path, cap], status); pst.click(safe_post, [path, cap], status)
        return vid, cap, mk, rv, cover, path

    with gr.Blocks(title="AI Reels Studio") as app:
        gr.Markdown("# 🎬 AI Reels Studio\nType what to teach → **Run** → a finished reel with caption, cover, SEO pack and a beginner review.")
        with gr.Tab("▶️ Make a reel"):
            with gr.Row():
                with gr.Column(scale=2):
                    prompt = gr.Textbox(label="What should this reel teach?", placeholder="Machine Learning kya hai?  /  Deepfake kaise pehchaanein?", lines=2)
                    run1 = gr.Button("▶️ Run", variant="primary", size="lg")
                    log1 = gr.Textbox(label="Progress", lines=16, max_lines=16, autoscroll=True)
                with gr.Column(scale=3): out1 = result_panel()
            run1.click(run_single, prompt, [log1, *out1])
        with gr.Tab("📚 Playlist"):
            with gr.Row():
                with gr.Column(scale=2):
                    subject = gr.Textbox(label="Playlist subject (new)", placeholder="AI from zero: the full story, from the first computers to today")
                    with gr.Row():
                        n = gr.Slider(5, 100, value=30, step=1, label="Episodes in the playlist")
                        now = gr.Number(1, label="Make now", minimum=1, maximum=100, precision=0)
                    sid = gr.Dropdown(series_ids(), label="…or continue an existing playlist", interactive=True)
                    run2 = gr.Button("▶️ Run", variant="primary", size="lg")
                    log2 = gr.Textbox(label="Progress", lines=10, max_lines=10, autoscroll=True)
                    eps = gr.Dataframe(headers=["#", "Era", "Title", "Status"], interactive=False, wrap=True)
                    ep_detail = gr.Markdown()
                with gr.Column(scale=3): out2 = result_panel()
            run2.click(run_playlist, [subject, n, now, sid], [log2, sid, eps, *out2])
            sid.change(ep_rows, sid, eps); eps.select(pick_ep, sid, ep_detail)
        with gr.Tab("🗂 History") as hist_tab:
            with gr.Row():
                with gr.Column(scale=2): runs = gr.Dataframe(history(), headers=["Run", "Title", "Series", "Status"], interactive=False, wrap=True)
                with gr.Column(scale=3): out3 = result_panel()
            hist_tab.select(history, None, runs); runs.select(pick_run, None, list(out3))
    app.queue().launch(inbrowser=True, theme=gr.themes.Soft(primary_hue="amber"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ui"
    {"ui": lambda: print("The UI is now the web app: run ./start.sh"), "auto": auto, "channels": channels, "make": lambda: make(" ".join(sys.argv[2:])),
     "resume": lambda: make("", d=sys.argv[2])}[cmd]()
