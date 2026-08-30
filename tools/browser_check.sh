#!/usr/bin/env bash
# Run the in-browser checks in headless Chrome.
#
# The page posts its results back to the local server rather than being scraped with
# --dump-dom. An earlier version used --dump-dom with --virtual-time-budget, which hangs:
# virtual time does not advance predictably while real network fetches are outstanding, and
# the Pyodide download is a large one, so Chrome never reached the point of dumping.
set -uo pipefail
cd "$(dirname "$0")/.."

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || { echo "Google Chrome not found at $CHROME"; exit 2; }

# This runs against a local copy only. Pointing it at a deployed site does not work: Chrome's
# Private Network Access rules block a page served from a public origin from reaching 127.0.0.1,
# so the results can never come back. tools/verify_deployment.py checks the published site
# instead, by comparing what Pages serves against the files these checks ran on.
PORT=${PORT:-8731}
RESULTS=$(mktemp -t browsercheck)
python3 tools/check_server.py "$PORT" "$RESULTS" &
SERVER=$!
PROFILE=$(mktemp -d)
cleanup() { kill "$SERVER" 2>/dev/null; pkill -f "user-data-dir=$PROFILE" 2>/dev/null; rm -rf "$PROFILE"; }
trap cleanup EXIT

for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$PORT/index.html" -o /dev/null && break
  sleep 0.25
done

"$CHROME" --headless --disable-gpu --no-sandbox --no-first-run --disable-dev-shm-usage \
  --user-data-dir="$PROFILE" \
  "http://127.0.0.1:$PORT/tests/browser-check.html" >/dev/null 2>&1 &
CHROME_PID=$!

DEADLINE=$(( $(date +%s) + ${TIMEOUT:-420} ))
while [ ! -s "$RESULTS" ]; do
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "The page did not report within the timeout. Chrome may have failed to load a module."
    kill "$CHROME_PID" 2>/dev/null
    exit 1
  fi
  sleep 1
done
kill "$CHROME_PID" 2>/dev/null; wait "$CHROME_PID" 2>/dev/null

python3 - "$RESULTS" <<'PY'
import json, sys
results = json.load(open(sys.argv[1]))
failed = 0
for r in results:
    if r.get("skipped"):
        print(f"  skip   {r['name']}  ({r['detail']})")
    elif r["ok"]:
        print(f"  pass   {r['name']}" + (f"  ({r['detail']})" if r["detail"] else ""))
    else:
        failed += 1
        print(f"  FAIL   {r['name']}\n         {r['detail']}")
print()
skipped = sum(1 for r in results if r.get("skipped"))
print(f"{len(results) - failed - skipped} passed, {skipped} skipped, {failed} failed.")
sys.exit(1 if failed else 0)
PY
