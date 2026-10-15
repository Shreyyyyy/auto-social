#!/bin/sh
# ./start.sh            -> UI in browser
# ./start.sh auto       -> next topic -> Buffer (use this in cron)
# ./start.sh make "..." -> render only
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"  # cron needs claude, uv, ffmpeg
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v uv >/dev/null || brew install uv
command -v npx >/dev/null || brew install node
[ -d video/node_modules ] || (cd video && npm install --silent)
[ -f .env ] || { cp .env.example .env; echo "Add GEMINI_API_KEY and BUFFER_TOKEN to .env, then run again."; exit 1; }
exec uv run reel.py "$@"
