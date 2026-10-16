#!/bin/sh
# ./start.sh            -> web app (http://localhost:3737) + API (http://127.0.0.1:8787)
# ./start.sh auto       -> next approved playlist episode -> Buffer (cron)
# ./start.sh make "..." -> make one reel from the command line
# ./start.sh resume out/<run> | channels
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"  # cron needs claude, uv, ffmpeg, node
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v uv >/dev/null || brew install uv
command -v npx >/dev/null || brew install node
[ -d video/node_modules ] || (cd video && npm install --silent)
[ -f .env ] || { cp .env.example .env; echo "Add GEMINI_API_KEY (and BUFFER_TOKEN to post) to .env, then run again."; exit 1; }
if [ $# -gt 0 ]; then exec uv run reel.py "$@"; fi

[ -d web/node_modules ] || (cd web && npm install --silent)
[ -d web/.next ] || (cd web && npm run build --silent)
for port in 3737 8787; do  # stop an older copy of this app still holding our ports
  pids=$(lsof -ti tcp:$port -sTCP:LISTEN 2>/dev/null); [ -n "$pids" ] && kill $pids 2>/dev/null && sleep 1
done
uv run server.py & API=$!
trap 'kill $API 2>/dev/null' EXIT INT TERM
(for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:8787/api/runs && break; sleep 1; done; open http://localhost:3737) &
cd web && npm run start --silent
