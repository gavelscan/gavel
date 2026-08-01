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

git add site/src/app/feed.json site/src/app/deployers.json \
        site/public/v1 gavel/rhj_registry.json
if git diff --cached --quiet; then
  say "no change at this block; nothing to publish"
  exit 0
fi

HEAD_BLOCK=$(python3 -c "import json;print(json.load(open('data/feed.json'))['head'])")
git -c user.name=gavelscan -c user.email=gavelscan@users.noreply.github.com \
    commit -q -m "data: record refreshed at block ${HEAD_BLOCK}"
git push -q origin main
say "published at block ${HEAD_BLOCK}"
