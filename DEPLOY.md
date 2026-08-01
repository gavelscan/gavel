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
```

Then commit and push; Vercel rebuilds on push. Until the watcher runs
somewhere continuously, this is a manual step and the freshness chip in
the header is what keeps that honest.

## Custom domain

Point `gavelscan.xyz` at Vercel (A record or the CNAME Vercel provides in
Project → Settings → Domains). Deploy first, verify on the vercel.app URL,
attach the domain last.
