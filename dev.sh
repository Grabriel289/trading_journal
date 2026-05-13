#!/usr/bin/env bash
# CryptoJournal — one-command install + run.
#
# Usage:
#   ./dev.sh                  # install (if needed) + start backend + frontend
#   ./dev.sh --install-only   # just install dependencies, don't start servers
#   ./dev.sh --reset          # wipe .venv, node_modules, and the SQLite DB
set -euo pipefail
cd "$(dirname "$0")"

INSTALL_ONLY=0
RESET=0
for arg in "$@"; do
    case "$arg" in
        --install-only) INSTALL_ONLY=1 ;;
        --reset)        RESET=1 ;;
        -h|--help)
            sed -n '2,8p' "$0"; exit 0 ;;
        *)
            echo "unknown flag: $arg"; exit 2 ;;
    esac
done

if [ "$RESET" -eq 1 ]; then
    echo "→ Wiping .venv, frontend/node_modules, data/cryptojournal.db"
    rm -rf .venv frontend/node_modules frontend/dist data/cryptojournal.db
    exit 0
fi

# ---------- toolchain detection ----------
PYTHON_BIN=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        ver=$("$cand" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")') || continue
        major=${ver%%.*}; minor=${ver##*.}
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_BIN="$cand"
            break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Python 3.10+ not found. Install Python 3.12 (recommended) and re-run." >&2
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js not found. Install Node 18+ and re-run." >&2
    exit 1
fi
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
if [ "$NODE_MAJOR" -lt 18 ]; then
    echo "ERROR: Node 18+ required (found $NODE_MAJOR)." >&2
    exit 1
fi

# ---------- backend deps ----------
if [ ! -d .venv ]; then
    echo "→ Creating Python venv ($PYTHON_BIN)"
    "$PYTHON_BIN" -m venv .venv
fi
REQ_HASH_FILE=".venv/.requirements.hash"
REQ_HASH=$(shasum -a 1 requirements.txt | awk '{print $1}')
if [ ! -f "$REQ_HASH_FILE" ] || [ "$(cat "$REQ_HASH_FILE")" != "$REQ_HASH" ]; then
    echo "→ Installing Python dependencies"
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    echo "$REQ_HASH" > "$REQ_HASH_FILE"
fi

# ---------- frontend deps ----------
PKG_HASH_FILE="frontend/node_modules/.package.hash"
PKG_HASH=$(shasum -a 1 frontend/package.json | awk '{print $1}')
if [ ! -d frontend/node_modules ] \
   || [ ! -f "$PKG_HASH_FILE" ] \
   || [ "$(cat "$PKG_HASH_FILE" 2>/dev/null || echo)" != "$PKG_HASH" ]; then
    echo "→ Installing frontend dependencies"
    (cd frontend && npm install --silent)
    echo "$PKG_HASH" > "$PKG_HASH_FILE"
fi

if [ "$INSTALL_ONLY" -eq 1 ]; then
    echo "✔ Install complete. Run ./dev.sh to start the app."
    exit 0
fi

# ---------- run ----------
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if lsof -nP -iTCP:"$BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $BACKEND_PORT already in use." >&2; exit 1
fi
if lsof -nP -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $FRONTEND_PORT already in use." >&2; exit 1
fi

# Apply any pending Alembic migrations before the server starts.
# Fresh installs: this creates every table. Existing installs: no-op if at head.
echo "→ Applying schema migrations (alembic upgrade head)"
if ! .venv/bin/alembic upgrade head 2>&1 | tee /tmp/cj-alembic-out.log; then
    # If alembic_version points at a revision that no longer exists in the
    # migrations folder (happens when a previous install half-failed before
    # the squashed-migration fix), the safest recovery is to wipe the DB —
    # there's no user data because tables were never fully created.
    if grep -q "Can't locate revision" /tmp/cj-alembic-out.log; then
        echo
        echo "⚠ Alembic state references a revision that no longer exists." >&2
        echo "  This usually means a previous install failed before completing." >&2
        echo "  Wiping the half-built DB and retrying…" >&2
        rm -f data/cryptojournal.db
        .venv/bin/alembic upgrade head || { echo "Migration still failing — see error above." >&2; exit 1; }
    else
        echo "Migration failed — see error above." >&2
        exit 1
    fi
fi
rm -f /tmp/cj-alembic-out.log

echo "→ Starting backend on http://localhost:$BACKEND_PORT"
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload &
BACKEND_PID=$!

cleanup() {
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo
        echo "→ Stopping backend (pid $BACKEND_PID)"
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
}
trap cleanup INT TERM EXIT

# Wait for backend health
for _ in $(seq 1 30); do
    if curl -fs "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

cat <<EOF

==================================================
 CryptoJournal is running
   Frontend: http://localhost:$FRONTEND_PORT
   Backend:  http://localhost:$BACKEND_PORT/docs
   Stop:     Ctrl+C
==================================================
EOF

# Auto-open the dashboard in the default browser once Vite is likely ready.
# Set NO_BROWSER=1 to disable (useful over SSH / CI / headless boxes).
if [ "${NO_BROWSER:-0}" != "1" ]; then
    (
        sleep 4
        url="http://localhost:$FRONTEND_PORT"
        if command -v open >/dev/null 2>&1; then
            open "$url" 2>/dev/null || true              # macOS
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$url" 2>/dev/null || true          # Linux
        elif command -v wslview >/dev/null 2>&1; then
            wslview "$url" 2>/dev/null || true           # WSL
        fi
    ) &
fi

cd frontend && npm run dev
