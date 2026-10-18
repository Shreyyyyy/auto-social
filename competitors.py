"""Competitor research for the channel's niche: find the most-viewed short explainers, keep only real competitors,
look at the top ones (frames + captions, Claude vision) and write research/playbook.md that every script follows.

  uv run --with ... python competitors.py     (or the Refresh button on the Competitors page)
Uses the YouTube Data API when YOUTUBE_API_KEY is set, otherwise public YouTube search data (yt-dlp).
"""
import concurrent.futures as cf
import json, re, subprocess, tempfile, time, urllib.parse
from pathlib import Path

import requests

import reel
from pydantic import BaseModel

from reel import C, E

DIR = Path("research")
QUERIES = C.get("competitor_queries") or [
    "AI kya hai", "ChatGPT kaise kaam karta hai", "AI explained in hindi", "artificial intelligence hindi", "deepfake kya hai",
    "AI tools hindi", "technology explained hindi", "AI facts hindi", "machine learning hindi", "AI news hindi", "AI se paise kaise kamaye",
    "ChatGPT hindi", "AI scam hindi", "AI kaise kaam karta hai"]
MIN_VIEWS = int(E("COMPETITOR_MIN_VIEWS", "1000000"))


# ---------- YouTube sign-in for research: OAuth desktop flow, READ-ONLY scope, refresh token kept locally ----------
TOKEN = Path(E("YOUTUBE_TOKEN_FILE", ".youtube_token.json"))
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"  # can search/read; can never upload or change anything


def youtube_auth():
    """One-time: opens Google's consent page in the browser, catches the code on 127.0.0.1, saves the refresh token."""
    import http.server, secrets, socketserver, webbrowser
    cid, secret = E("YOUTUBE_CLIENT_ID"), E("YOUTUBE_CLIENT_SECRET")
    if not (cid and secret): raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET missing in .env")
    got, state = {}, secrets.token_urlsafe(16)

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<h2>YouTube connected for research (read-only). You can close this tab.</h2>")
        def log_message(self, *a): pass
    with socketserver.TCPServer(("127.0.0.1", 0), H) as srv:
        redirect = f"http://127.0.0.1:{srv.server_address[1]}"
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE, "access_type": "offline",
            "prompt": "consent", "state": state})
        print("opening Google sign-in (read-only YouTube access for research)...\n" + url); webbrowser.open(url)
        srv.timeout, deadline = 5, time.time() + 300  # give up after 5 minutes instead of waiting forever
        while "code" not in got and "error" not in got and time.time() < deadline: srv.handle_request()
    if "code" not in got and "error" not in got: raise RuntimeError("sign-in timed out (5 min) - press Connect YouTube again")
    if got.get("error") or got.get("state") != state: raise RuntimeError(f"sign-in failed: {got.get('error', 'state mismatch')}")
    t = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={"client_id": cid, "client_secret": secret, "code": got["code"],
                      "redirect_uri": redirect, "grant_type": "authorization_code"}).json()
    if "refresh_token" not in t: raise RuntimeError(f"no refresh token: {t}")
    TOKEN.write_text(json.dumps({"refresh_token": t["refresh_token"], "access_token": t["access_token"], "expires": time.time() + t.get("expires_in", 3600) - 60}))
    TOKEN.chmod(0o600); print("YouTube connected (read-only).")
    return True


def youtube_token():
    """A valid access token from the saved refresh token, or None."""
    if not TOKEN.exists(): return None
    t = json.loads(TOKEN.read_text())
    if time.time() < t.get("expires", 0): return t["access_token"]
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={"client_id": E("YOUTUBE_CLIENT_ID"), "client_secret": E("YOUTUBE_CLIENT_SECRET"),
                      "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).json()
    if "access_token" not in r: return None
    t.update(access_token=r["access_token"], expires=time.time() + r.get("expires_in", 3600) - 60); TOKEN.write_text(json.dumps(t))
    return t["access_token"]


def _yt(path, params):
    """Official YouTube Data API call: signed in (OAuth, read-only) or with YOUTUBE_API_KEY."""
    tok = youtube_token()
    r = requests.get(f"https://www.googleapis.com/youtube/v3/{path}", timeout=30, params=params if tok else params | {"key": E("YOUTUBE_API_KEY")},
                     headers={"Authorization": f"Bearer {tok}"} if tok else {}).json()
    if "error" in r: raise RuntimeError(r["error"]["message"][:200])
    return r


def official_api(): return bool(E("YOUTUBE_API_KEY") or TOKEN.exists())


def _api_search(q):
    """YouTube Data API: most-viewed Shorts in India for a query."""
    r = _yt("search", {"part": "snippet", "q": q, "type": "video", "videoDuration": "short", "order": "viewCount", "regionCode": "IN",
                       "relevanceLanguage": "hi", "maxResults": 50})
    if "error" in r: raise RuntimeError(r["error"]["message"][:200])
    ids = [i["id"]["videoId"] for i in r.get("items", [])]
    if not ids: return []
    v = _yt("videos", {"part": "statistics,contentDetails,snippet", "id": ",".join(ids)})
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
    search = _api_search if official_api() else _public_search
    print(f"searching YouTube ({'official API' if official_api() else 'public data'}) for {len(QUERIES)} niche queries...")
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
    """Claude reads titles/channels and keeps only real competitors: AI / tech explainers for Indian (Hindi) audiences."""
    listing = "\n".join(f"{i}. [{c['channel']}] {c['title']} ({c['views']:,} views, {c['duration']}s)" for i, c in enumerate(cands[:120]))
    prompt = (f"Our channel: {C['niche']} for {C['audience']} in {C['region']}, in Hindi/Hinglish.\nBelow are popular YouTube Shorts. "
              "Keep ONLY real competitors: videos that explain AI or technology to the GENERAL PUBLIC / beginners in an engaging way "
              "(creator explainers, news explainers, viral 'what is X' videos). EXCLUDE university/engineering lectures, syllabus or exam "
              "topics (BFS/DFS, hyperparameters, neural network math), coding tutorials, kids cartoons, songs, pranks, product ads, unrelated "
              "news and 'artificial insemination'. Prefer Hindi/Hinglish creators for Indian audiences and higher views; at most 2 per channel. "
              f'Return JSON {{"keep": [{{"index": i, "why": "short"}}]}} best first, max {limit}.\n\n' + listing)
    keep = reel.ask(prompt, Keep).keep
    kept = [cands[k.index] | {"why_competitor": k.why} for k in keep if 0 <= k.index < len(cands)]
    return sorted(kept, key=lambda v: -v["views"])[:limit]


class Pick(BaseModel):
    index: int
    why: str = ""


class Keep(BaseModel):
    keep: list[Pick]


class Playbook(BaseModel):
    bullets: list[str]


ASK = """You are the head of growth at a top short-form education studio. Study this Short closely: below are frames through it
(with times) and what is said (auto captions). Reply with JSON only: "first_1s" (what is seen and heard), "hook_words" (exact opening words), "hook_type", "teaching_method" (step by step),
"visual_style" (footage/animation/face/screen/text, cuts per 10s), "voice" (tone, pace, emotion), "retention_tricks" (list),
"ending" (and whether it loops), "share_trigger", "why_it_worked" (3 biggest reasons), "steal" (3 concrete things a Hindi reel
teaching AI to beginners should copy), "avoid" (what it does badly)."""


def captions(vtt):
    """Plain text from a .vtt file (timestamps, tags and the rolling duplicates of auto captions removed)."""
    out = []
    for ln in vtt.splitlines():
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if ln and "-->" not in ln and not ln.startswith(("WEBVTT", "Kind:", "Language:")) and (not out or out[-1] != ln): out.append(ln)
    return " ".join(out)


def analyse(v, frames=10):
    """Download the Short small, take frames through it + its auto captions, and have a vision model break it down."""
    try:
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(["uvx", "--quiet", "yt-dlp", "--no-warnings", "-f", "worst[ext=mp4]/worst", "--write-auto-subs", "--write-subs",
                            "--sub-langs", "hi.*,en.*", "--sub-format", "vtt", "-o", f"{t}/v.%(ext)s", f"https://www.youtube.com/shorts/{v['id']}"],
                           capture_output=True, timeout=300)
            vid = next(Path(t).glob("v.mp4"), None) or next(Path(t).glob("v.*[!t]"), None)
            if not vid: return v | {"analysis": None}
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vid)],
                                       capture_output=True, text=True).stdout or v.get("duration") or 30)
            shots = []
            for k in range(frames):
                at = dur * (k + 0.5) / frames
                b = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(vid), "-frames:v", "1", "-vf", "scale=360:-2",
                                    "-f", "image2", "-c:v", "mjpeg", "-"], capture_output=True).stdout
                if b: shots.append((f"{at:.1f}s:", b))
            said = " ".join(captions(f.read_text(errors="ignore")) for f in Path(t).glob("*.vtt"))[:6000] or "(no captions)"
        return v | {"analysis": reel.vision_json(f"{ASK}\n\nTitle: {v['title']} ({v['channel']}, {dur:.0f}s)\nWhat is said: {said}",
                                                 shots, f"competitor watch ({len(shots)} frames)")}
    except Exception as e:
        print(f"  could not analyse {v['id']}: {e}")
        return v | {"analysis": None}


def write_playbook(videos):
    """Turn the analyses into one short playbook the script writer follows."""
    body = json.dumps([{"title": v["title"], "channel": v["channel"], "views": v["views"], "analysis": v["analysis"]} for v in videos if v.get("analysis")],
                      ensure_ascii=False)[:60000]
    prompt = ("These are the most-viewed competitor Shorts in our niche and an analysis of each. Write a concise VIRAL PLAYBOOK "
              f"(max 14 bullet points) for our Hindi AI Case File reels for {C['audience']}: what to do in the first second, hooks that "
              "work (with 2-3 real example openings), teaching moves, pacing, visuals, endings, share triggers, and what to avoid. "
              "Be specific, cite which video each lesson came from. One bullet per item in `bullets`.\n\n" + body)
    return "\n".join("- " + b.lstrip("- ") for b in reel.ask(prompt, Playbook).bullets)


def refresh(top=10):
    reel.USAGE.clear()
    kept = keep_competitors(candidates())
    print(f"kept {len(kept)} real competitors - studying the top {min(top, len(kept))}...")
    with cf.ThreadPoolExecutor(4) as ex: watched = list(ex.map(analyse, kept[:top]))
    watched += kept[top:]
    print("writing the playbook...")
    playbook = write_playbook(watched)
    DIR.mkdir(exist_ok=True)
    data = {"updated": time.strftime("%Y-%m-%d %H:%M"), "source": "YouTube Data API" if official_api() else "public YouTube data",
            "min_views": min(v["views"] for v in watched) if watched else MIN_VIEWS, "videos": watched, "usage": reel.usage_summary()}
    (DIR / "competitors.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    (DIR / "playbook.md").write_text(f"# Viral playbook ({data['updated']}, from {len(watched)} competitor Shorts)\n\n{playbook}\n")
    print(f"done - paid ${data['usage']['paid_usd']:.3f}")
    return {"competitors": len(watched)}


if __name__ == "__main__":
    import sys
    youtube_auth() if sys.argv[1:] == ["auth"] else refresh()
