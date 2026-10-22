#!/usr/bin/env bash
# Test server with a COPY of the data – never test against the real data.
#
#   tools/testserver.sh <port> <work-dir> [--auth [--user <account>]] [--web <dir>] [--family]
#
# Copies data/ to <work-dir>/data (only the first time), switches off auto-apply and folder watching
# there, and starts Tuttiphon without schedules on 127.0.0.1:<port>.
#   --auth        turn on sign-in (a random administrator password in the copy, as if set in the browser) and print
#                 session cookies:
#                 admin = local administrator, user = a user account (--user <account>, otherwise TUTTIPHON_TEST_USER
#                 from dev.local.env, otherwise the first user account of the copied configuration)
#   --web <dir>   own build folder (otherwise web/ in the project) – e.g. after `npx vite build --outDir <dir>`
#   --family      the copy gets a family (only in its configuration – no account in Navidrome, nothing is written
#                 there) if it has none yet (e2e)
# TUTTIPHON_TEST_DATA (dev.local.env or the environment): copy this data folder instead of data/ – say, a backup of
# another instance unpacked somewhere else
# Output with --auth: the lines "admin-cookie: tuttiphon=…" and "user-cookie:  tuttiphon=…" (tests/e2e/setup.js reads them).
# Stop: PID from `ss -ltnp | grep :<port>` – never pkill -f.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
port="${1:?port missing}"; work="${2:?work dir missing}"; shift 2
# Personal settings (not in Git): TUTTIPHON_BASE (Navidrome folder), TUTTIPHON_TEST_USER (account for --auth),
# TUTTIPHON_TEST_DATA (data folder to copy)
if [ -f dev.local.env ]; then set -a; . ./dev.local.env; set +a; fi
auth=0; family=0; web="$PWD/web"; user="${TUTTIPHON_TEST_USER:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --auth) auth=1 ;;
    --family) family=1 ;;
    --web) web="$(readlink -f "$2")"; shift ;;
    --user) user="$2"; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done
mkdir -p "$work"
data="$(readlink -f "$work")/data"
# Data source: TUTTIPHON_TEST_DATA or data/ here – in a Git worktree without data/, the one of the main checkout
src="${TUTTIPHON_TEST_DATA:-data}"
if [ -z "${TUTTIPHON_TEST_DATA:-}" ] && [ ! -d "$src" ] && common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
  src="$(dirname "$common")/data"
fi
[ -d "$src" ] || { echo "No data found ($src)." >&2; exit 1; }
if [ ! -d "$data" ]; then
  cp -a "$src" "$data"
  python3 - "$data/config.json" <<'PY'
import json, sys
p = sys.argv[1]; c = json.load(open(p)); s = c["settings"]
s["autoApply"] = False
w = s.get("watch") if isinstance(s.get("watch"), dict) else {}
w["enabled"] = False; s["watch"] = w
json.dump(c, open(p, "w"), ensure_ascii=False, indent=1)
PY
fi
if [ "$family" = 1 ]; then
  TUTTIPHON_DATA="$data" TUTTIPHON_SHARED_DIR="$(readlink -f "$work")/shared" python3 - <<'PY'
from app import config
def family(c):   # as POST /api/family, without the Navidrome account (the copy never writes to Navidrome)
    if any(p.get("family") for p in c["personen"]):
        return
    ids = {p["id"] for p in c["personen"]}
    c["personen"].append({"id": next(x for x in ["familie"] + [f"familie-{n}" for n in range(2, 100)] if x not in ids),
                          "name": "Familie", "icon": "i:home", "user": "tuttiphon-test-familie", "family": True,
                          "clean": True, "prefix": "", "likes": {"welten": [], "stile": [], "artists": []},
                          "dislikes": {"artists": [], "genres": []}})
config.update_config(family)
PY
fi
# TUTTIPHON_SHARED_DIR: instance registration and run lock in the work dir instead of the real playlist folder
export TUTTIPHON_DATA="$data" TUTTIPHON_NO_SCHEDULER=1 TUTTIPHON_WEB="$web" \
       TUTTIPHON_SHARED_DIR="$(readlink -f "$work")/shared"
[ -n "${TUTTIPHON_BASE:-}" ] && export TUTTIPHON_BASE
if [ "$auth" = 1 ]; then
  python3 - "$user" <<'PY'
import secrets, sys
from app import auth, config, localadmin
if not localadmin.configured():   # sign-in needs the local administrator's password – a random one for the copy
    localadmin.set_password("test-" + secrets.token_hex(6))
cfg = config.load_config()
# the account for the "user" role: given, otherwise the first user account of the configuration
user = sys.argv[1] or next((a for a, v in (cfg.get("accounts") or {}).items() if (v or {}).get("role") == "user"), "") \
    or next((p["user"] for p in cfg["personen"] if p.get("user")), "")
print("admin-cookie: tuttiphon=" + auth.make_token(auth.NOTFALL))
if user:
    print("user-cookie:  tuttiphon=" + auth.make_token(user))
PY
fi
nohup python3 tuttiphon.py serve --port "$port" --no-browser >"$work/server-$port.log" 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 0.5
  if ss -ltn | grep -q ":$port "; then echo "running: http://127.0.0.1:$port/ (log: $work/server-$port.log)"; exit 0; fi
done
echo "Start failed – see $work/server-$port.log" >&2; exit 1
