# auto-social — fun teacher Reels that explain any concept

`reel.py` (pipeline + UI) + `video/` (Remotion template) + `config.json` (channel: niche, audience, language, voice, colours).
Type what to teach → **Run** → a finished reel + cover + caption + SEO/marketing pack + a beginner review.

Pipeline (per reel, ~6-9 min):
1. **Research** - Gemini + Google Search: what you asked, latest news (your location first), trends, what people ask, verified facts, analogies, SEO keywords.
2. **Script** - Claude (Claude Code login; Gemini fallback) as a fun, patient teacher: hook → concept → analogy → how it works → real news → myth vs truth → "Yaad rakho" → loop-back ending. Built on a playbook from 13 Shorts with 10M-38M views (`research/competitors_10M.json`). Mechanical checks (card numbers must be spoken, charts complete).
3. **Voice** - Gemini TTS directed like a teacher's voice session (emotion per line), 2 takes, Gemini listens and keeps the most human one.
4. **Visuals** - real footage from Coverr (+ Pexels with `PEXELS_KEY`), Gemini checks every clip actually matches the line; teaching moments on a bright whiteboard (definition, step diagrams, self-drawing charts, phone chat demo, recap); lighter cards float over footage. No generated images.
5. **Edit** - Remotion: creator captions, countdown promise, source chips, SFX, Lyria music; clean grid-safe cover.
6. **Review** - two Gemini "beginner viewers" watch the finished reel (what they learned + scores + timestamped problems); one automatic revision if needed, and the better version is kept.
7. **Marketing pack** (`marketing.md`) - keyword-first caption, 3-5 hashtags, alt text, first comment, story + broadcast lines, best IST time, first-hour checklist (`research/instagram_reach.md`).
8. **You approve / post** - Buffer posting only after your approval; duplicates refused.

## Make it about anything
Edit `config.json`: `niche`, `audience`, `region`, `spoken_language`, `caption_language`, `tts_language_code`, `tone`, `examples`, `duration_seconds`, `voice` (Gemini voice name), `series_hashtag`, `fallback_footage`, `theme` colours.

## Setup (once)
```
brew install ffmpeg uv node   # start.sh does this + npm install for you
cp .env.example .env      # add GEMINI_API_KEY (+ BUFFER_TOKEN to post)
```

## Run
`./start.sh` → **AI Reels Studio** at http://127.0.0.1:7860
- **▶️ Make a reel**: type what it should teach → **Run** → reel, cover, caption, SEO pack, review → Approve / Post.
- **📚 Playlist**: subject + number of episodes → **Run** (plans the whole story, makes the first N); pick it again later to make the next ones.
- **🗂 History**: every reel with status (awaiting approval / approved / queued / failed).

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
