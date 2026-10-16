#!/bin/bash
# ==============================================================================
# AI Reels Studio
#
# Usage:
#   ./start.sh            -> Docker (if running): API + web in containers -> http://localhost:3737
#   ./start.sh local      -> Without Docker: API (:8787) + web app on this machine
#   ./start.sh dev        -> Without Docker, Next.js hot-reload dev server
#   ./start.sh logs       -> Follow the Docker logs
#   ./start.sh stop       -> Stop everything (Docker containers and local servers)
#   ./start.sh build      -> Rebuild the Next.js web application
#   ./start.sh auto       -> Post next approved episode to Buffer (cron)
#   ./start.sh make "..." -> Generate a reel from the command line
#   ./start.sh resume <path> -> Resume rendering a specific run
# ==============================================================================

set -eo pipefail
cd "$(dirname "$0")"

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

API_PORT="${API_PORT:-8787}"
WEB_PORT="${PORT:-3737}"

# PIDs listening on a port, minus Docker's own port forwarder (never kill Docker Desktop)
port_pids() {
  for pid in $(lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null || true); do
    ps -o comm= -p "$pid" 2>/dev/null | grep -qiE "docker|vpnkit" || echo "$pid"
  done
}

stop_services() {
  local stopped=0
  for port in "$WEB_PORT" "$API_PORT"; do
    local pids
    pids=$(port_pids "$port")
    if [ -n "$pids" ]; then
      stopped=1
      # Send SIGTERM first
      kill $pids 2>/dev/null || true
      sleep 0.5
      # Force kill if still holding port
      local stubborn
      stubborn=$(port_pids "$port")
      if [ -n "$stubborn" ]; then
        kill -9 $stubborn 2>/dev/null || true
      fi
    fi
  done
  if [ "$stopped" -eq 1 ]; then
    echo -e "${GREEN}✓ Stopped all active servers on ports :$WEB_PORT and :$API_PORT${RESET}"
  else
    echo -e "${CYAN}No running servers found on ports :$WEB_PORT or :$API_PORT${RESET}"
  fi
}

docker_ok() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

# Subcommand: stop
if [ "$1" = "stop" ]; then
  docker_ok && [ -n "$(docker compose ps -q 2>/dev/null)" ] && docker compose down && echo -e "${GREEN}✓ Stopped the Docker containers${RESET}"
  stop_services
  exit 0
fi

if [ "$1" = "logs" ]; then exec docker compose logs -f --tail 100; fi

# Docker mode (default when Docker is running)
if [ "$1" = "docker" ] || { [ $# -eq 0 ] && docker_ok; }; then
  docker_ok || { echo -e "${RED}Docker is not running - start Docker Desktop, or use ./start.sh local${RESET}"; exit 1; }
  if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${RED}Created .env - add GEMINI_API_KEY (and BUFFER_TOKEN for posting), then run again.${RESET}"; exit 1
  fi
  stop_services >/dev/null  # free the ports if the local version is running
  mkdir -p out series research assets
  [ -f .youtube_token.json ] && [ ! -f research/.youtube_token.json ] && cp .youtube_token.json research/.youtube_token.json
  STUDIO_PASSWORD=$(grep -E '^STUDIO_PASSWORD=' .env | cut -d= -f2- || true)
  echo -e "${CYAN}Building and starting containers (first build takes a few minutes)...${RESET}"
  docker compose up --build -d
  for _ in $(seq 1 120); do curl -s -o /dev/null "http://localhost:$WEB_PORT" && break; sleep 1; done
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
  echo -e "${BOLD}${GREEN}========================================${RESET}"
  echo -e "${BOLD}${GREEN}     AI Reels Studio (Docker) running    ${RESET}"
  echo -e "${BOLD}${GREEN}========================================${RESET}"
  echo -e "  ${BOLD}This computer:${RESET} ${CYAN}http://localhost:$WEB_PORT${RESET}"
  [ -n "$LAN_IP" ] && echo -e "  ${BOLD}Phone (same Wi-Fi):${RESET} ${CYAN}http://$LAN_IP:$WEB_PORT${RESET}"
  [ -z "$STUDIO_PASSWORD" ] && echo -e "  ${YELLOW}No STUDIO_PASSWORD set - anyone on your network can open the studio.${RESET}"
  echo -e "  ${BOLD}Logs:${RESET} ./start.sh logs    ${BOLD}Stop:${RESET} ./start.sh stop"
  command -v open >/dev/null 2>&1 && open "http://localhost:$WEB_PORT"
  exit 0
fi
[ "$1" = "local" ] && shift

# Ensure standard binaries in PATH
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Check required dependencies
check_dep() {
  local cmd="$1"
  local pkg="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      echo -e "${YELLOW}Installing missing dependency: $pkg...${RESET}"
      brew install "$pkg"
    else
      echo -e "${RED}Error: '$cmd' is not installed and Homebrew was not found.${RESET}"
      echo "Please install $pkg and try again."
      exit 1
    fi
  fi
}

check_dep ffmpeg ffmpeg
check_dep uv uv
check_dep node node

# Node module installations
if [ ! -d "video/node_modules" ]; then
  echo -e "${CYAN}Installing Remotion dependencies (video/)...${RESET}"
  (cd video && npm install --silent)
fi

# Environment check
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "${YELLOW}Created .env from .env.example.${RESET}"
  echo -e "${RED}Please add GEMINI_API_KEY (and BUFFER_TOKEN if posting) to .env, then run again.${RESET}"
  exit 1
fi

# Passthrough commands to reel.py (unless dev or build)
if [ "$1" = "build" ]; then
  echo -e "${CYAN}Building Next.js frontend...${RESET}"
  cd web && npm run build
  exit 0
elif [ $# -gt 0 ] && [ "$1" != "dev" ]; then
  exec uv run reel.py "$@"
fi

# Ensure web dependencies and build
if [ ! -d "web/node_modules" ]; then
  echo -e "${CYAN}Installing web dependencies (web/)...${RESET}"
  (cd web && npm install --silent)
fi

MODE="${1:-prod}"
# Rebuild when there is no build yet, or any web source changed since the last one
if [ "$MODE" = "prod" ] && { [ ! -f "web/.next/BUILD_ID" ] || \
   [ -n "$(find web/app web/components web/lib web/tailwind.config.js web/next.config.mjs web/package.json -newer web/.next/BUILD_ID -print -quit 2>/dev/null)" ]; }; then
  echo -e "${CYAN}Web code changed - building for production...${RESET}"
  (cd web && npm run build --silent) || { echo -e "${YELLOW}Build failed - fix the errors above${RESET}"; exit 1; }
fi

# Clear any stale instances before launching
for port in "$WEB_PORT" "$API_PORT"; do
  pids=$(port_pids "$port")
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    sleep 0.5
    stubborn=$(port_pids "$port")
    [ -n "$stubborn" ] && kill -9 $stubborn 2>/dev/null || true
  fi
done

# Start FastAPI backend
uv run server.py &
API_PID=$!

cleanup() {
  echo -e "\n${YELLOW}Shutting down servers...${RESET}"
  kill "$API_PID" 2>/dev/null || true
  # Kill child processes of API
  pkill -P "$API_PID" 2>/dev/null || true
  for port in "$WEB_PORT" "$API_PORT"; do
    pids=$(port_pids "$port")
    [ -n "$pids" ] && kill $pids 2>/dev/null || true
  done
  exit 0
}
trap cleanup EXIT INT TERM

# Wait for the API before starting the web app (avoids ECONNREFUSED noise while uv starts Python)
for _ in $(seq 1 60); do
  curl -s -o /dev/null "http://127.0.0.1:$API_PORT/api/runs" 2>/dev/null && break
  kill -0 "$API_PID" 2>/dev/null || { echo -e "${YELLOW}API failed to start - see the error above${RESET}"; exit 1; }
  sleep 0.5
done

# Background worker to wait for both services before launching browser
(
  for _ in $(seq 1 45); do
    if curl -s -o /dev/null "http://127.0.0.1:$API_PORT/api/runs" 2>/dev/null && \
       curl -s -o /dev/null "http://localhost:$WEB_PORT" 2>/dev/null; then
      if command -v open >/dev/null 2>&1; then
        open "http://localhost:$WEB_PORT"
      fi
      break
    fi
    sleep 0.8
  done
) &

echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "${BOLD}${GREEN}        AI Reels Studio Started         ${RESET}"
echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "  ${BOLD}API Backend:${RESET}  ${CYAN}http://127.0.0.1:$API_PORT${RESET}"
echo -e "  ${BOLD}Web Studio:${RESET}   ${CYAN}http://localhost:$WEB_PORT${RESET}"
echo -e "  ${BOLD}Mode:${RESET}         ${YELLOW}$([ "$MODE" = "dev" ] && echo "Development (live reload)" || echo "Production")${RESET}"
echo -e "  ${BOLD}Stop servers:${RESET} Press ${BOLD}Ctrl+C${RESET} or run ${CYAN}./start.sh stop${RESET}"
echo -e "${GREEN}----------------------------------------${RESET}\n"

if [ "$MODE" = "dev" ]; then
  cd web && npm run dev
else
  cd web && npm run start --silent
fi
