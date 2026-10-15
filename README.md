# auto-social — universal news-explainer Reels

`reel.py` (pipeline + UI) + `video/` (Remotion template) + `config.json` (what your channel is about).
~30s reels that look like a real creator's edit:
1. **Gemini + Google Search** researches the topic: fresh news, verified numbers, real questions, SEO keywords.
2. **Claude** (your Claude Code login; Gemini fallback) writes one narrator script: hook, lines, a filmable stock-footage scene per line, 2-4 data cards, source per fact, SEO pack.
3. **Gemini TTS** narrates (Google Cloud TTS Chirp 3 HD is used automatically if enabled for your key). **Lyria 3** makes the music.
4. **Coverr** real footage, full screen, a new scene every line (cv2-animated Coverr still only if a clip fails). No generated images, no presenters or characters.
5. **Remotion** edits: hard cuts, hook headline, creator-style captions, white data cards, 📰 source chips, subtle SFX.
6. **You approve** each reel; only then Buffer posts it (cloudinary/catbox hosting). Duplicates are refused.

## Make it about anything
Edit `config.json`: `niche`, `audience`, `region`, `spoken_language`, `caption_language`, `tts_language_code`, `tone`, `examples`, `duration_seconds`, `voice` (Gemini voice name), `series_hashtag`, `fallback_footage`, `theme` colours.

## Setup (once)
```
brew install ffmpeg uv node   # start.sh does this + npm install for you
cp .env.example .env      # add GEMINI_API_KEY (+ BUFFER_TOKEN to post)
```

## Run
`./start.sh` → **AI Reels Studio** at http://127.0.0.1:7860
- **⚡ Single reel**: one-line idea → *Research & plan* (Gemini + Google Search researches, Claude writes a timed beat sheet + example + psychology) → edit → *Generate* → *Post*.
- **📚 Series / playlist**: subject + episodes (5-100) → *Research & plan series* (history → today → future, each with a news hook + teaser) → *Generate next X* when you want.
- **🗂 History**: every reel with its status (awaiting approval / approved / queued / failed). *Approve for scheduled post* or *Post now*.

Daily job (`crontab -e`) - approval-gated: posts the next episode only if you approved that exact video; otherwise it generates it and waits for you (series = latest, or `SERIES=<id>` in .env):
```
0 19 * * * ~/coding/personal/auto-social/start.sh auto >> ~/coding/personal/auto-social/auto.log 2>&1
```
Data lives in `out/<run>/` (reel, script, meta) and `series/<id>.json`.

## Posting via Buffer (once)
No Instagram/Meta token needed - Buffer handles Instagram.
1. In Buffer, connect your Instagram as a **Business/Creator** account (needed for auto-publishing reels).
2. Buffer → Settings → API → create an API key → `BUFFER_TOKEN` in `.env`.
3. `./start.sh channels` → copy the instagram line's `BUFFER_CHANNEL_ID` into `.env`.
4. Buffer needs a public video URL: each reel is uploaded to Cloudinary if `CLOUDINARY_URL` is set (recommended), else catbox.moe.
5. `BUFFER_MODE=addToQueue` drops reels into your Buffer time slots; `shareNow` posts immediately.

## Tweak
- Channel identity → `config.json`. Writing rules → `BRIEF` in reel.py. Look → `video/src/Reel.tsx` (colours from `config.json` → `theme`).
- Every run keeps `research.txt`, `script.json`, voice lines, clips and `meta.json` in `out/<time>/`; `./start.sh resume out/<time>` re-renders without paying again.
