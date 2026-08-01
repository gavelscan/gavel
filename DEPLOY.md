# Deploying the site

The site is a Next.js static export: `next build` writes `out/`, which is
plain HTML, CSS, JS and the JSON API. It needs no server at runtime.

## Vercel

Import `gavelscan/gavel` and set:

| Setting | Value |
|---|---|
| Root directory | `site` |
| Framework preset | Next.js |
| Build command | `npm run build` |
| Output directory | `out` |
| Install command | `npm install` |

`site/vercel.json` adds CORS and cache headers to `/v1/*` so the JSON can
be read from other origins — that is the point of publishing it.

Nothing secret is needed at build time. The site reads the chain from the
browser for the freshness indicator only, over a public RPC.

## Refreshing the data

The pages are built from a snapshot, and the header says how old that
snapshot is. To cut a fresh one:

```bash
python3 -m gavel.watch --backfill      # pull new events into the archive
python3 scripts/build_feed.py          # rebuild the feed + deployer index
cp data/feed.json site/src/app/feed.json
cp data/deployers.json site/src/app/deployers.json
python3 scripts/build_api.py           # rewrite site/public/v1
python3 scripts/build_hero.py          # homepage figures and hero field
```

Or run all of it with one command:

```bash
bash scripts/refresh.sh
```

It pushes only when the record actually moved, and Vercel rebuilds on
that push.

### Keeping it running on this Mac

```bash
mkdir -p ~/Library/LaunchAgents
sed "s|REPO_PATH|$PWD|g" scripts/xyz.gavelscan.refresh.plist \
  > ~/Library/LaunchAgents/xyz.gavelscan.refresh.plist
launchctl load ~/Library/LaunchAgents/xyz.gavelscan.refresh.plist
```

Check on it:

```bash
launchctl list | grep gavelscan     # is it registered
tail -f logs/refresh.log            # what it did last
launchctl start xyz.gavelscan.refresh   # force a run now
```

Stop it:

```bash
launchctl unload ~/Library/LaunchAgents/xyz.gavelscan.refresh.plist
```

launchd skips ticks while the machine is asleep and fires once on wake,
so a closed laptop shows up as a widening gap in the header rather than
as a site quietly pretending to be current. `.github/workflows/refresh.yml`
runs the same steps on GitHub's schedule and acts as a floor under that —
leave both on; whichever runs first finds nothing for the other to do.

Pushing from launchd needs git credentials that work without a terminal
prompt. The gh CLI's credential helper already provides that if `gh auth
status` shows the gavelscan account.

## Custom domain

Point `gavelscan.xyz` at Vercel (A record or the CNAME Vercel provides in
Project → Settings → Domains). Deploy first, verify on the vercel.app URL,
attach the domain last.
