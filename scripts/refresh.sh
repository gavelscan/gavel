#!/bin/bash
# One refresh of the published record.
#
# Pull new events, rebuild everything derived from them, and push only if
# the record actually moved. Vercel redeploys on that push. Safe to run
# from launchd, from CI, or by hand — a lock keeps two runs from racing
# the archive cursor.

set -euo pipefail
cd "$(dirname "$0")/.."

LOCK="data/.refresh.lock"
mkdir -p data logs
exec 9>"$LOCK"
if ! flock -n 9 2>/dev/null; then
  # macOS has no flock(1); fall back to a pid file.
  if [ -f data/.refresh.pid ] && kill -0 "$(cat data/.refresh.pid)" 2>/dev/null; then
    echo "$(date -u +%FT%TZ) another refresh is running; skipping"
    exit 0
  fi
fi
echo $$ > data/.refresh.pid
trap 'rm -f data/.refresh.pid' EXIT

# Local config (extra RPC endpoints, keys) lives in a gitignored .env.
# Read as data, not sourced: values legitimately contain characters the
# shell would try to interpret, and a config file should never be able to
# run commands.
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    key=${line%%=*}
    val=${line#*=}
    case "$key" in *[!A-Za-z0-9_]*) continue ;; esac
    val=${val%\"}; val=${val#\"}
    val=${val%\'}; val=${val#\'}
    export "$key=$val"
  done < .env
fi

say() { echo "$(date -u +%FT%TZ) $*"; }

say "pulling new events"
python3 -m gavel.watch --backfill

say "refreshing the issuer registry"
# A stale registry reads as unknown, never as a false verified badge, so a
# failed fetch must not abort the refresh.
python3 -m gavel.registry || say "registry refresh failed; keeping the cached copy"

say "rebuilding feed, deployers and API"
python3 scripts/build_feed.py
python3 scripts/build_deployers.py
cp data/feed.json site/src/app/feed.json
cp data/deployers.json site/src/app/deployers.json
python3 scripts/build_api.py
python3 scripts/build_hero.py

git add site/src/app/feed.json site/src/app/deployers.json \
        site/src/app/launches.json site/public/v1 gavel/rhj_registry.json
if git diff --cached --quiet; then
  say "no change at this block; nothing to publish"
  exit 0
fi

HEAD_BLOCK=$(python3 -c "import json;print(json.load(open('data/feed.json'))['head'])")
git -c user.name=gavelscan -c user.email=gavelscan@users.noreply.github.com \
    commit -q -m "data: record refreshed at block ${HEAD_BLOCK}"

# Two writers publish this record (this machine and the Actions cron).
# If the other one pushed first, reconcile instead of wedging: the files
# in conflict are all generated, and the copy this run just built from
# the chain is by definition the current one, so conflicts take ours.
# Without this, a single divergence silently stopped every later push —
# nineteen refreshes once piled up locally while the site aged.
if ! git push -q origin main 2>/dev/null; then
  say "remote moved; reconciling"
  git fetch -q origin
  git -c user.name=gavelscan -c user.email=gavelscan@users.noreply.github.com \
      merge -q -X ours origin/main -m "merge: reconcile concurrent refresh writers"
  git push -q origin main
fi
say "published at block ${HEAD_BLOCK}"
