# auto-social — Hindi AI explainer Reels

`reel.py` (pipeline + UI) + `video/` (one Remotion template). ~30s Gen-Z motion-graphics reels in ~2 min:
1. **Claude** (your Claude Code login) researches + writes: hook, Priya ↔ Sharma Uncle Hindi dialogue, and a typed visual per line (hook, flow, counter, compare, stamp, list, video, image, emoji, quote).
2. **Gemini TTS** (your `GEMINI_API_KEY`) voices each line; auto speed-up to fit 30s.
3. **Lyria 3** (same Gemini key) makes background music (or drop your own `music.mp3` in the folder).
4. **Coverr** stock video (B-roll, credited in the caption) + **Openverse** CC0 photos styled with **cv2** (contrast, neon duotone, glow, vignette, grain). No AI image generation.
5. **Remotion** (`video/src/Reel.tsx`) animates it all: word-by-word karaoke captions, self-building flowcharts, counters, VS cards, stamps, facecam bubbles, progress bar, open-loop sticker, end card, synced SFX.
6. catbox.moe upload → Buffer → Instagram.

## Setup (once)
```
brew install ffmpeg uv node   # start.sh does this + npm install for you
cp .env.example .env      # add GEMINI_API_KEY (+ BUFFER_TOKEN to post)
```

## Run
`./start.sh` → **AI Reels Studio** at http://127.0.0.1:7860
- **⚡ Single reel**: one-line idea → *Research & plan* (Claude searches current news, writes a timed 30s beat sheet + example + psychology) → edit → *Generate* → *Post*.
- **📚 Series / playlist**: subject + episodes (5-100) → *Research & plan series* (history → today → future, each with a news hook + teaser) → *Generate next X* when you want.
- **🗂 History**: every reel ever made, play it, edit caption, post; posted status is tracked.

Daily auto-post (`crontab -e`) - posts the next unposted episode of the latest series (or `SERIES=<id>` in .env):
```
0 19 * * * ~/coding/personal/auto-social/start.sh auto >> ~/coding/personal/auto-social/auto.log 2>&1
```
Data lives in `out/<run>/` (reel, script, meta) and `series/<id>.json`.

## Posting via Buffer (once)
No Instagram/Meta token needed - Buffer handles Instagram.
1. In Buffer, connect your Instagram as a **Business/Creator** account (needed for auto-publishing reels).
2. Buffer → Settings → API → create an API key → `BUFFER_TOKEN` in `.env`.
3. `./start.sh channels` → copy the instagram line's `BUFFER_CHANNEL_ID` into `.env`.
4. Nothing else: Buffer only accepts a public video URL, so each reel is auto-uploaded to catbox.moe (free, no account).
5. `BUFFER_MODE=addToQueue` drops reels into your Buffer time slots; `shareNow` posts immediately.

## Tweak
- Writing rules → `BRIEF`. Animation/look → `video/src/Reel.tsx` (colours at the top). Photo grade → `stock_image()`. Hosts & voices → `CAST`; facecam photos → `assets/priya.png`, `assets/uncle.png`.
- Curriculum → `topics.txt` (Bag of Words → Transformers → ChatGPT → Agents → future).
- Every run saves `script.json`, images and audio in `out/<time>/` so you can fix one scene and re-render it.
