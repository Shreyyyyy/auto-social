"""Competitor research for the channel's niche: find the most-viewed short explainers, keep only real competitors,
watch the top ones with Gemini, and write research/playbook.md that every script follows.

  uv run --with ... python competitors.py     (or the Refresh button on the Competitors page)
Uses the YouTube Data API when YOUTUBE_API_KEY is set, otherwise public YouTube search data (yt-dlp).
"""
import concurrent.futures as cf
import json, re, subprocess, time, urllib.parse
from pathlib import Path

import requests

import reel
from reel import C, E, GEMINI, GKEY, RESEARCH_MODEL, track

DIR = Path("research")
QUERIES = C.get("competitor_queries") or [
    "AI kya hai", "ChatGPT kaise kaam karta hai", "AI explained in hindi", "artificial intelligence hindi", "deepfake kya hai",
    "AI tools hindi", "technology explained hindi", "AI facts hindi", "machine learning hindi", "AI news hindi", "AI se paise kaise kamaye",
    "ChatGPT hindi", "AI scam hindi", "AI kaise kaam karta hai"]
MIN_VIEWS = int(E("COMPETITOR_MIN_VIEWS", "1000000"))


def _api_search(q):
    """YouTube Data API: most-viewed Shorts in India for a query (needs YOUTUBE_API_KEY)."""
    key = E("YOUTUBE_API_KEY")
    r = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=30, params={
        "part": "snippet", "q": q, "type": "video", "videoDuration": "short", "order": "viewCount", "regionCode": "IN",
        "relevanceLanguage": "hi", "maxResults": 50, "key": key}).json()
    if "error" in r: raise RuntimeError(r["error"]["message"][:200])
    ids = [i["id"]["videoId"] for i in r.get("items", [])]
    if not ids: return []
    v = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=30, params={
        "part": "statistics,contentDetails,snippet", "id": ",".join(ids), "key": key}).json()
    out = []
    for x in v.get("items", []):
        m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", x["contentDetails"]["duration"]) or None
        secs = (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0
        out.append({"id": x["id"], "title": x["snippet"]["title"], "channel": x["snippet"]["channelTitle"], "views": int(x["statistics"].get("viewCount", 0)),
                    "likes": int(x["statistics"].get("likeCount", 0)), "duration": secs, "published": x["snippet"]["publishedAt"][:10]})
    return out


def _public_search(q):
    """No key: YouTube's own 'sort by view count, under 4 minutes' search results via yt-dlp."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}&sp=CAMSAhgB"
    lines = subprocess.run(["uvx", "--quiet", "yt-dlp", "--flat-playlist", "--no-warnings", "--playlist-end", "40", "--print",
                            "%(id)s\t%(view_count)s\t%(duration)s\t%(channel)s\t%(title)s", url], capture_output=True, text=True, timeout=300).stdout
    out = []
    for ln in lines.splitlines():
        p = ln.split("\t")
        if len(p) == 5 and p[1].isdigit():
            out.append({"id": p[0], "views": int(p[1]), "duration": int(float(p[2])) if p[2] not in ("NA", "") else 0, "channel": p[3], "title": p[4]})
    return out


def candidates():
    search = _api_search if E("YOUTUBE_API_KEY") else _public_search
    print(f"searching YouTube ({'official API' if E('YOUTUBE_API_KEY') else 'public data'}) for {len(QUERIES)} niche queries...")
    with cf.ThreadPoolExecutor(4) as ex: found = [v for r in ex.map(search, QUERIES) for v in r]
    for floor in (MIN_VIEWS, 300_000, 100_000):  # this niche is small: widen the bar until there is enough to choose from
        seen, out = set(), []
        for v in sorted(found, key=lambda v: -v["views"]):
            if v["id"] in seen or v["views"] < floor or not (0 < v["duration"] <= 180): continue
            seen.add(v["id"]); out.append(v)
        if len(out) >= 25: break
    print(f"  {len(found)} results -> {len(out)} short videos with {floor:,}+ views")
    return out


def keep_competitors(cands, limit=12):
    """Gemini reads titles/channels and keeps only real competitors: AI / tech explainers for Indian (Hindi) audiences."""
    listing = "\n".join(f"{i}. [{c['channel']}] {c['title']} ({c['views']:,} views, {c['duration']}s)" for i, c in enumerate(cands[:120]))
    prompt = (f"Our channel: {C['niche']} for {C['audience']} in {C['region']}, in Hindi/Hinglish.\nBelow are popular YouTube Shorts. "
              "Keep ONLY real competitors: videos that explain AI or technology to the GENERAL PUBLIC / beginners in an engaging way "
              "(creator explainers, news explainers, viral 'what is X' videos). EXCLUDE university/engineering lectures, syllabus or exam "
              "topics (BFS/DFS, hyperparameters, neural network math), coding tutorials, kids cartoons, songs, pranks, product ads, unrelated "
              "news and 'artificial insemination'. Prefer Hindi/Hinglish creators for Indian audiences and higher views; at most 2 per channel. "
              f'Return JSON {{"keep": [{{"index": i, "why": "short"}}]}} best first, max {limit}.\n\n' + listing)
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=180,
                      json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}).json()
    track("competitor filter", RESEARCH_MODEL, r)
    keep = json.loads(r["candidates"][0]["content"]["parts"][0]["text"]).get("keep", [])
    kept = [cands[k["index"]] | {"why_competitor": k.get("why", "")} for k in keep if isinstance(k.get("index"), int) and k["index"] < len(cands)]
    return sorted(kept, key=lambda v: -v["views"])[:limit]


ASK = """You are the head of growth at a top short-form education studio. Watch this Short closely (picture and sound).
Reply JSON: "first_1s" (what is seen and heard), "hook_words" (exact opening words), "hook_type", "teaching_method" (step by step),
"visual_style" (footage/animation/face/screen/text, cuts per 10s), "voice" (tone, pace, emotion), "retention_tricks" (list),
"ending" (and whether it loops), "share_trigger", "why_it_worked" (3 biggest reasons), "steal" (3 concrete things a Hindi reel
teaching AI to beginners should copy), "avoid" (what it does badly)."""


def analyse(v):
    for _ in range(3):
        r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=900, json={"contents": [{"parts": [
            {"fileData": {"fileUri": f"https://www.youtube.com/watch?v={v['id']}"}}, {"text": ASK}]}],
            "generationConfig": {"responseMimeType": "application/json", "mediaResolution": "MEDIA_RESOLUTION_LOW"}}).json()
        track("competitor watch", RESEARCH_MODEL, r)
        try: return v | {"analysis": json.loads(r["candidates"][0]["content"]["parts"][0]["text"])}
        except Exception: time.sleep(10)
    return v | {"analysis": None}


def write_playbook(videos):
    """Turn the analyses into one short playbook the script writer follows."""
    body = json.dumps([{"title": v["title"], "channel": v["channel"], "views": v["views"], "analysis": v["analysis"]} for v in videos if v.get("analysis")],
                      ensure_ascii=False)[:60000]
    prompt = ("These are the most-viewed competitor Shorts in our niche and an analysis of each. Write a concise VIRAL PLAYBOOK "
              f"(max 14 bullet points) for our Hindi AI Case File reels for {C['audience']}: what to do in the first second, hooks that "
              "work (with 2-3 real example openings), teaching moves, pacing, visuals, endings, share triggers, and what to avoid. "
              "Be specific, cite which video each lesson came from. Plain text bullets starting with '- '.\n\n" + body)
    r = requests.post(f"{GEMINI}/{RESEARCH_MODEL}:generateContent", headers=GKEY(), timeout=300,
                      json={"contents": [{"parts": [{"text": prompt}]}]}).json()
    track("playbook", RESEARCH_MODEL, r)
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])


def refresh(top=10):
    reel.USAGE.clear()
    kept = keep_competitors(candidates())
    print(f"kept {len(kept)} real competitors - watching the top {min(top, len(kept))} with Gemini...")
    with cf.ThreadPoolExecutor(4) as ex: watched = list(ex.map(analyse, kept[:top]))
    watched += kept[top:]
    print("writing the playbook...")
    playbook = write_playbook(watched)
    DIR.mkdir(exist_ok=True)
    data = {"updated": time.strftime("%Y-%m-%d %H:%M"), "source": "YouTube Data API" if E("YOUTUBE_API_KEY") else "public YouTube data",
            "min_views": min(v["views"] for v in watched) if watched else MIN_VIEWS, "videos": watched, "usage": reel.usage_summary()}
    (DIR / "competitors.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    (DIR / "playbook.md").write_text(f"# Viral playbook ({data['updated']}, from {len(watched)} competitor Shorts)\n\n{playbook}\n")
    print(f"done - Gemini ${data['usage']['gemini_usd']:.3f}")
    return {"competitors": len(watched)}


if __name__ == "__main__":
    refresh()
