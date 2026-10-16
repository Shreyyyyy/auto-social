# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi", "uvicorn", "requests", "python-dotenv", "opencv-python-headless", "numpy", "pydantic"]
# ///
"""HTTP API for the web app (web/). Wraps reel.py: one job at a time, live logs, runs, playlists, approve/post.

  uv run server.py      # http://127.0.0.1:8787  (start.sh runs this together with the Next.js app)
"""
import contextlib, io, json, threading, time, uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import reel

app = FastAPI(title="AI Reels Studio API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3737", "http://127.0.0.1:3737"], allow_methods=["*"], allow_headers=["*"])
reel.OUT.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=reel.OUT), name="media")

JOBS: dict[str, dict] = {}
CURRENT: list[str] = []  # id of the running job (one at a time - the pipeline is heavy)


class Stopped(Exception): pass


class _Log(io.TextIOBase):
    """Job log - and the stop switch: once a job is cancelled, its next print raises and unwinds the pipeline."""
    def __init__(self, job): self.job = job
    def write(self, x):
        if self.job.get("cancel"): raise Stopped("stopped by you")
        self.job["log"] = (self.job["log"] + x)[-20000:]; return len(x)


def kill_children():
    """Stop every process this API started (Claude, voice/render, ffmpeg) - the whole tree."""
    import os, signal, subprocess as sp
    def tree(pid):
        kids = [int(k) for k in sp.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()]
        return kids + [g for k in kids for g in tree(k)]
    for pid in reversed(tree(os.getpid())):
        try: os.kill(pid, signal.SIGTERM)
        except ProcessLookupError: pass


def start_job(kind: str, label: str, fn, *args) -> dict:
    if CURRENT and JOBS[CURRENT[0]]["status"] == "running":
        raise HTTPException(409, f"Another job is running: {JOBS[CURRENT[0]]['label']}")
    job = {"id": uuid.uuid4().hex[:10], "kind": kind, "label": label, "status": "running", "log": "", "result": None,
           "error": None, "started": time.time()}
    JOBS[job["id"]] = job; CURRENT[:] = [job["id"]]

    def run():
        try:
            with contextlib.redirect_stdout(_Log(job)): job["result"] = fn(*args)
            job["status"] = "done"
        except Exception as e:
            if job.get("cancel"): job["status"], job["error"] = "stopped", "Stopped by you"
            else: job["status"], job["error"] = "error", f"{type(e).__name__}: {e}"
        job["ended"] = time.time()
    threading.Thread(target=run, daemon=True).start()
    return public(job)


def public(job):
    r = job.get("result")
    if isinstance(r, tuple) and r and isinstance(r[0], str): r = {"run": Path(r[0]).parent.name}
    elif isinstance(r, dict) and "id" in r: r = {"playlist": r["id"]}
    return {k: v for k, v in job.items() if k != "result"} | {"result": r}


# ---------------- runs (every reel ever made) ----------------
def run_summary(d: Path) -> dict:
    m = json.loads((d / "meta.json").read_text())
    rv = m.get("review") or {}
    return {"id": d.name, "title": m.get("title"), "status": "queued" if m.get("posted") else m.get("status", "awaiting approval"),
            "series": m.get("series"), "ep": m.get("ep"), "voice": m.get("voice"), "verdict": rv.get("verdict"), "scores": rv.get("scores"),
            "cover": f"/media/{d.name}/cover.jpg" if (d / "cover.jpg").exists() else None, "video": f"/media/{d.name}/reel.mp4"}


@app.get("/api/runs")
def runs():
    return [run_summary(m.parent) for m in sorted(reel.OUT.glob("*/meta.json"), key=lambda f: f.parent.name, reverse=True)
            if (m.parent / "reel.mp4").exists()]


@app.get("/api/runs/{rid}")
def run_detail(rid: str):
    d = reel.OUT / rid
    if not (d / "meta.json").exists(): raise HTTPException(404, "no such reel")
    m = json.loads((d / "meta.json").read_text())
    read = lambda f: (d / f).read_text() if (d / f).exists() else None
    if not (d / "contact.jpg").exists() and (d / "props.json").exists():
        try: reel.contact_sheet(d)  # older reels get one on first view
        except Exception: pass
    return run_summary(d) | {"sent": reel.sent_to(m), "send_errors": m.get("buffer_errors") or {}, "contact": f"/media/{d.name}/contact.jpg" if (d / "contact.jpg").exists() else None, "caption": m.get("caption"), "marketing": read("marketing.md"), "research": read("research.txt"),
                             "review": json.loads(read("review.json")) if read("review.json") else None,
                             "script": json.loads(read("script.json")) if read("script.json") else None, "meta": m,
                             "usage": json.loads(read("usage.json")) if read("usage.json") else None}


class Caption(BaseModel):
    caption: str
    channels: list[str] | None = None  # networks to post to (instagram, youtube, linkedin); None = all


@app.delete("/api/runs/{rid}")
def delete_run(rid: str):
    """Delete a reel. If it belonged to a playlist, that episode goes back to 'scripted' so it can be made again."""
    import shutil
    d = reel.OUT / rid
    if not d.is_dir() or "/" in rid or ".." in rid: raise HTTPException(404, "no such reel")
    if CURRENT and JOBS[CURRENT[0]]["status"] == "running" and rid in JOBS[CURRENT[0]].get("log", ""): raise HTTPException(409, "this reel is being made - stop it first")
    m = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    if m.get("series"):
        try:
            sr = reel.load(m["series"]); e = sr["episodes"][m["ep"] - 1]
            if e.get("video") and Path(e["video"]).parent.name == rid: e.update(status="scripted" if e.get("script") else "planned", video=None); reel.save(sr)
        except Exception: pass
    shutil.rmtree(d)
    return {"message": "Deleted"}


@app.delete("/api/playlists/{sid}")
def delete_playlist(sid: str, delete_videos: bool = False):
    """Delete a playlist (its finished videos stay in the Library unless delete_videos=True)."""
    import shutil
    f = reel.SERIES / f"{sid}.json"
    if not f.exists() or "/" in sid or ".." in sid: raise HTTPException(404, "no such playlist")
    if delete_videos:
        try:
            sr = json.loads(f.read_text())
            for ep in sr.get("episodes", []):
                if ep.get("video"):
                    run_dir = Path(ep["video"]).parent
                    if run_dir.exists() and run_dir.is_dir() and run_dir.parent.resolve() == reel.OUT.resolve():
                        shutil.rmtree(run_dir)
        except Exception:
            pass
    f.unlink()
    return {"message": "Playlist deleted" + (" and all its video files removed" if delete_videos else "")}


@app.post("/api/runs/{rid}/approve")
def approve(rid: str, body: Caption):
    return {"message": reel.approve(str(reel.OUT / rid / "reel.mp4"), body.caption)}


@app.post("/api/runs/{rid}/post")
def post(rid: str, body: Caption):  # an explicit click = approval of this exact video + caption
    v = str(reel.OUT / rid / "reel.mp4")
    try: reel.approve(v, body.caption); return {"message": reel.post(v, body.caption, body.channels)}
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")


CHANNELS: dict = {}


@app.get("/api/channels")
def channels():
    """Buffer channels reels are posted to (cached for 10 minutes)."""
    if time.time() - CHANNELS.get("at", 0) > 600:
        try: CHANNELS.update(at=time.time(), list=[{"id": c["id"], "name": c["name"], "service": c["service"]} for c in reel.buffer_channels()])
        except Exception as e: raise HTTPException(502, f"Buffer: {e}")
    return CHANNELS["list"]


# ---------------- jobs ----------------
class Prompt(BaseModel):
    prompt: str
    channels: list[str] | None = None


@app.post("/api/reels")
def make_reel(body: Prompt):
    if not body.prompt.strip(): raise HTTPException(400, "Type what the reel should teach")
    return start_job("reel", body.prompt.strip()[:80], reel.make, body.prompt.strip())


def autopilot(make, channels=None):
    """One click: research -> script -> reel (make()) -> approve -> Buffer. Clicking it is the approval."""
    video, caption = make()
    verdict = (json.loads((Path(video).parent / "meta.json").read_text()).get("review") or {}).get("verdict")
    print(f"sending to Buffer: {', '.join(channels) if channels else 'all channels'} (review verdict: {verdict or 'n/a'})...")
    try:
        reel.approve(video, caption); print(reel.post(video, caption, channels))
    except Exception as e:  # the reel is kept - it can be posted again from its page
        print(f"⚠ Buffer post failed: {e}")
    return video, caption


@app.post("/api/reels/autopilot")
def make_and_post(body: Prompt):
    if not body.prompt.strip(): raise HTTPException(400, "Type the topic")
    if body.channels is not None and not body.channels: raise HTTPException(400, "Pick at least one channel to post to")
    p = body.prompt.strip()
    return start_job("autopilot", "Autopilot: " + p[:70], autopilot, lambda: reel.make(p), body.channels)


@app.get("/api/jobs/current")
def current():
    return public(JOBS[CURRENT[0]]) if CURRENT else None


@app.post("/api/jobs/{jid}/stop")
def stop_job(jid: str):
    job = JOBS.get(jid)
    if not job or job["status"] != "running": raise HTTPException(400, "nothing running to stop")
    job["cancel"] = True; kill_children()
    return {"message": "Stopping…"}


@app.get("/api/jobs/{jid}")
def job(jid: str):
    if jid not in JOBS: raise HTTPException(404, "no such job")
    return public(JOBS[jid])


# ---------------- playlists ----------------
def playlist_summary(sr):
    eps = sr["episodes"]
    return {"id": sr["id"], "name": sr["name"], "subject": sr.get("subject"), "created": sr.get("created"), "episodes": len(eps),
            "scripted": sum(1 for e in eps if e.get("script")), "made": sum(1 for e in eps if e["status"] in ("generated", "approved", "posted"))}


@app.get("/api/playlists")
def playlists():
    return [playlist_summary(reel.load(f.stem)) for f in sorted(reel.SERIES.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)]


class NewPlaylist(BaseModel):
    subject: str
    episodes: int = 10


@app.post("/api/playlists")
def new_playlist(body: NewPlaylist):
    if not body.subject.strip(): raise HTTPException(400, "Type the playlist subject")
    return start_job("playlist", f"Plan + {body.episodes} scripts: {body.subject[:60]}", reel.plan_series, body.subject.strip(), max(2, min(100, body.episodes)))


@app.get("/api/playlists/{sid}")
def playlist(sid: str):
    try: sr = reel.load(sid)
    except FileNotFoundError: raise HTTPException(404, "no such playlist")
    eps = []
    for i, e in enumerate(sr["episodes"]):
        rid = Path(e["video"]).parent.name if e.get("video") else None
        eps.append({"n": i + 1, "arc": e.get("arc", 0), "builds_on": e.get("builds_on") or ([i] if i else []),
                    "title": e["title"], "era": e.get("era"), "brief": e.get("brief"), "status": e["status"], "run": rid,
                    "cover": f"/media/{rid}/cover.jpg" if rid and (reel.OUT / rid / "cover.jpg").exists() else None,
                    "script": [{"say": l["caption"], "visual": l["visual"]["type"], "onscreen": l.get("onscreen", "")}
                               for l in (e.get("script") or {}).get("lines", [])],
                    "hook": (e.get("script") or {}).get("hook")})
    arcs = sr.get("arcs") or [{"title": "All episodes", "summary": sr.get("subject", "")}]
    return playlist_summary(sr) | {"episodes": eps, "arcs": arcs}


@app.post("/api/playlists/{sid}/episodes/{n}/run")
def run_episode(sid: str, n: int):
    sr = reel.load(sid)
    if not 1 <= n <= len(sr["episodes"]): raise HTTPException(404, "no such episode")
    return start_job("episode", f"{sr['name']} - episode {n}", reel.make_episode, sr, n - 1)


class Channels(BaseModel):
    channels: list[str] | None = None


@app.post("/api/playlists/{sid}/episodes/{n}/autopilot")
def autopilot_episode(sid: str, n: int, body: Channels):
    """Make one episode and post it to the chosen channels, in one go."""
    sr = reel.load(sid)
    if not 1 <= n <= len(sr["episodes"]): raise HTTPException(404, "no such episode")
    if body.channels is not None and not body.channels: raise HTTPException(400, "Pick at least one channel to post to")
    return start_job("autopilot", f"Autopilot: {sr['name']} - episode {n}", autopilot, lambda: reel.make_episode(sr, n - 1), body.channels)


@app.post("/api/playlists/{sid}/episodes/{n}/script")
def write_script(sid: str, n: int):
    """(Re)write one episode's script without making the video."""
    def go():
        sr = reel.load(sid); print(f"writing script {n}...")
        sr["episodes"][n - 1].update(script=reel.write_episode_script(sr, n - 1, sr.get("notes", "")), status="scripted"); reel.save(sr)
        print("done"); return {"id": sid}
    return start_job("script", f"Script for episode {n}", go)


# ---------------- competitors ----------------
@app.get("/api/competitors")
def competitors_data():
    f, pb = Path("research/competitors.json"), Path("research/playbook.md")
    data = json.loads(f.read_text()) if f.exists() else {"videos": []}
    import competitors
    return data | {"playbook": pb.read_text() if pb.exists() else None, "api_key": competitors.official_api(),
                   "youtube_connected": competitors.TOKEN.exists()}


YT = {"status": "idle", "error": None}


@app.post("/api/youtube/connect")
def youtube_connect():
    """Opens Google's consent page (read-only YouTube scope, research only) in this computer's browser.
    Runs on its own - it never blocks reel or playlist jobs."""
    import competitors
    if YT["status"] == "waiting": return YT
    def go():
        YT.update(status="waiting", error=None)
        try: competitors.youtube_auth(); YT["status"] = "connected"
        except Exception as e: YT.update(status="failed", error=str(e))
    threading.Thread(target=go, daemon=True).start()
    return {"status": "waiting", "error": None}


@app.get("/api/youtube/status")
def youtube_status():
    import competitors
    return YT | {"connected": competitors.TOKEN.exists()}


@app.post("/api/competitors/refresh")
def competitors_refresh():
    import competitors
    return start_job("competitors", "Competitor research + playbook", competitors.refresh)


if __name__ == "__main__":
    uvicorn.run(app, host=reel.E("API_HOST", "127.0.0.1"), port=int(reel.E("API_PORT", "8787")), log_level="warning")
