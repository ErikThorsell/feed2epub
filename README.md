# feed2epub

Turns a list of RSS/Atom feeds into daily, image-free EPUBs and serves them over OPDS for an e-reader to pull -- built
for an Xteink X4 running CrossPoint firmware, which can browse an OPDS catalog but cannot parse feeds itself.

Each run produces **one EPUB per feed** (one article per chapter), stripped of images and CSS down to semantic HTML so
the reader's own typography wins. Two containers share a library folder: a `fetcher` that rebuilds the EPUBs on a daily
loop and prunes old ones, and a `server` that publishes the folder as an OPDS acquisition catalog.

Feeds and options live in [`feeds.yaml`](feeds.yaml).

## Deploy

```bash
# One-time: the bind-mounted library must be writable by uid 1000.
sudo mkdir -p /mnt/container_volumes/feed2epub/library \
  && sudo chown -R 1000:1000 /mnt/container_volumes/feed2epub

docker compose up -d --build
```

Put a reverse proxy in front of the server (`http://<host>:8095`) and point your reader at `<proxy-url>/catalog.xml`.
