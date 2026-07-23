# feed2epub

Turns a list of RSS/Atom feeds into daily, image-free EPUBs and serves them over OPDS for an e-reader to pull -- built
for an Xteink X4 running CrossPoint firmware, which can browse an OPDS catalog but cannot parse feeds itself.

Each run produces **one EPUB per feed** (one article per chapter), stripped of images and CSS down to semantic HTML so
the reader's own typography wins. Two containers share a library folder: a `fetcher` that rebuilds the EPUBs on a daily
loop and prunes old ones, and a `server` that publishes the folder as an OPDS acquisition catalog.

Feeds and options are your **deployment config**, not part of the app: copy
[`feeds.example.yaml`](feeds.example.yaml) to `feeds.yaml` (gitignored) and edit it. A feed URL may reference a
secret as `${VAR}` (e.g. the tokenised Instapaper RSS URL as `${INSTAPAPER_FEED_URL}`), expanded from the
environment at load time — supplied via `.env` (Compose) or a Secret (Kubernetes).

## Deploy

Two supported targets, both driven from the same published image — see [`deployment/`](deployment/):

- **[Docker Compose](deployment/docker-compose/)** — single host, builds locally.
- **[Kubernetes](deployment/kubernetes/)** — cluster, pulls `ghcr.io/erikthorsell/feed2epub` (published by
  [`.github/workflows/publish.yaml`](.github/workflows/publish.yaml) on each `v*.*.*` tag).

Either way, put the OPDS server behind a reverse proxy / ingress and point your reader at
`<url>/catalog.xml`.
