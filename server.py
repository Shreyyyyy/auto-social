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


class _Log(io.TextIOBase):
    def __init__(self, job): self.job = job
    def write(self, x): self.job["log"] = (self.job["log"] + x)[-20000:]; return len(x)


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
            job["status"], job["error"] = "error", f"{type(e).__name__}: {e}"
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
    return run_summary(d) | {"caption": m.get("caption"), "marketing": read("marketing.md"), "research": read("research.txt"),
                             "review": json.loads(read("review.json")) if read("review.json") else None,
                             "script": json.loads(read("script.json")) if read("script.json") else None, "meta": m,
                             "usage": json.loads(read("usage.json")) if read("usage.json") else None}


class Caption(BaseModel):
    caption: str


@app.post("/api/runs/{rid}/approve")
def approve(rid: str, body: Caption):
    return {"message": reel.approve(str(reel.OUT / rid / "reel.mp4"), body.caption)}


@app.post("/api/runs/{rid}/post")
def post(rid: str, body: Caption):  # an explicit click = approval of this exact video + caption
    v = str(reel.OUT / rid / "reel.mp4")
    try: reel.approve(v, body.caption); return {"message": reel.post(v, body.caption)}
    except Exception as e: raise HTTPException(400, f"{type(e).__name__}: {e}")


# ---------------- jobs ----------------
class Prompt(BaseModel):
    prompt: str


@app.post("/api/reels")
def make_reel(body: Prompt):
    if not body.prompt.strip(): raise HTTPException(400, "Type what the reel should teach")
    return start_job("reel", body.prompt.strip()[:80], reel.make, body.prompt.strip())


@app.get("/api/jobs/current")
def current():
    return public(JOBS[CURRENT[0]]) if CURRENT else None


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
        eps.append({"n": i + 1, "title": e["title"], "era": e.get("era"), "brief": e.get("brief"), "status": e["status"], "run": rid,
                    "cover": f"/media/{rid}/cover.jpg" if rid and (reel.OUT / rid / "cover.jpg").exists() else None,
                    "script": [{"say": l["caption"], "visual": l["visual"]["type"], "onscreen": l.get("onscreen", "")}
                               for l in (e.get("script") or {}).get("lines", [])],
                    "hook": (e.get("script") or {}).get("hook")})
    return playlist_summary(sr) | {"episodes": eps}


@app.post("/api/playlists/{sid}/episodes/{n}/run")
def run_episode(sid: str, n: int):
    sr = reel.load(sid)
    if not 1 <= n <= len(sr["episodes"]): raise HTTPException(404, "no such episode")
    return start_job("episode", f"{sr['name']} - episode {n}", reel.make_episode, sr, n - 1)


@app.post("/api/playlists/{sid}/episodes/{n}/script")
def write_script(sid: str, n: int):
    """(Re)write one episode's script without making the video."""
    def go():
        sr = reel.load(sid); print(f"writing script {n}...")
        sr["episodes"][n - 1].update(script=reel.write_episode_script(sr, n - 1, sr.get("notes", "")), status="scripted"); reel.save(sr)
        print("done"); return {"id": sid}
    return start_job("script", f"Script for episode {n}", go)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(reel.E("API_PORT", "8787")), log_level="warning")
