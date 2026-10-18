# Katha (कथा) — topic in, reels everywhere

Any prompt becomes a researched, voiced, rendered reel (explainer, story, news, list, motivation, comedy...), posted to Instagram, YouTube and LinkedIn.
Runs on your Claude subscription + free tools only - no paid API keys.

`reel.py` (pipeline + UI) + `video/` (Remotion template) + `config.json` (channel: niche, audience, language, voice, colours).
Type what the reel should be → **Run** → a finished reel + cover + caption + SEO/marketing pack + a beginner review.

Pipeline (per reel, ~10-20 min):
1. **Research** - Claude Code + web search: what you asked and what kind of video it is, latest news, trend analysis, market research (top Shorts on the topic, saturated vs fresh angles), what people say, verified facts, tone & expressions that land, 5 scored hooks, SEO keywords.
2. **Script** - Claude picks the genre, the look (`casefile` for niche explainers, `story` for everything else), a persona and the best hook, then writes in the structure that genre's best videos use (explainers: hook → concept → analogy → how it works → real news → myth vs truth → "Yaad rakho"). Built on a playbook from 13 Shorts with 10M-38M views (`research/competitors_10M.json`). Mechanical checks (card numbers must be spoken, charts complete).
3. **Voice** - free, on your Mac (`tts_server.py`, started by `./start.sh`): one narrator voice acts every line's delivery note - VoxCPM2 for Hindi/English, OmniVoice for other Indian languages (winners of a 12-model listening test). Put a 10s recording of yourself in `assets/voice/narrator.wav` (+ its transcript in `narrator.txt`) to use your own voice. Edge TTS if the engine is off.
4. **Visuals** - *Story* look: full-screen real footage, punch-in cuts, bold word-by-word captions, proof cards over the footage. *AI Case File* look (explainers): a detective corkboard: every line pins a clue (real footage polaroid from Pixabay/Coverr/Pexels/Wikimedia CC0/Prelinger, an evidence card, or a sticky note with Google's animated emoji), red strings connect them, CASE SOLVED verdict. Claude checks every clip really matches the line. No generated images.
5. **Edit** - Remotion: camera glides clue to clue, countdown promise, source chips, risers/impacts/sparkles, free CC0 / CC BY music (Openverse); clean grid-safe cover.
6. **Review** - Claude watches the finished reel as a typical viewer (what they learned + scores + timestamped problems); one automatic revision if needed, and the better version is kept.
7. **Marketing pack** (`marketing.md`) - keyword-first caption, 3-5 hashtags, alt text, first comment, story + broadcast lines, best IST time, first-hour checklist (`research/instagram_reach.md`).
8. **You approve / post** - Buffer posting only after your approval; duplicates refused.

## Make it about anything
Edit `config.json`: `niche`, `audience`, `region`, `spoken_language`, `caption_language`, `tts_language_code`, `tone`, `examples`, `duration_seconds`, `voice` (Gemini voice name), `series_hashtag`, `fallback_footage`, `theme` colours.

## Setup (once)
```
brew install ffmpeg uv node   # start.sh does this + npm install for you
cp .env.example .env      # add BUFFER_TOKEN to post; Claude Code must be logged in (or CLAUDE_CODE_OAUTH_TOKEN for Docker)
```

## Run
`./start.sh` → **Case File Studio** at http://localhost:3737 (web app, Next.js) + API at http://127.0.0.1:8787 (`server.py`)
- **✨ New reel**: type what it should teach → **Run** → live progress → reel, cover, caption, review, script, SEO pack → Approve / Post.
- **📚 Playlists**: subject + number of episodes → all scripts are written first (read them any time). Under each episode: **Run case #N**.
  Make one a day: each run does fresh research, keeps only strong examples, and learns from the previous episode's review.
- **🎬 Library**: every reel with its status (awaiting approval / approved / queued / failed).
- Command line still works: `./start.sh make "..."`, `./start.sh resume out/<run>`, `./start.sh auto`, `./start.sh channels`.

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
