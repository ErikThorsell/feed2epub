# feed2epub on Docker Compose

```bash
cd deployment/docker-compose

# 1. Config (from the repo root): your feed list + optional secret.
cp ../../feeds.example.yaml ../../feeds.yaml   # then edit ../../feeds.yaml
cp ../../.env.example       ../../.env         # optional: fill in INSTAPAPER_FEED_URL

# 2. One-time: the bind-mounted library must be writable by uid 1000.
sudo mkdir -p /mnt/container_volumes/feed2epub/library \
  && sudo chown -R 1000:1000 /mnt/container_volumes/feed2epub

# 3. Up (builds the image locally).
docker compose up -d --build
```

Put a reverse proxy in front of the server (`http://<host>:8095`) and point your reader at
`<proxy-url>/catalog.xml`. Run a fetch immediately instead of waiting for the daily loop:

```bash
docker compose run --rm fetcher python -m feed2epub --config /config/feeds.yaml
```

Paths in `compose.yaml` are relative to this directory, so the build context and `feeds.yaml`/`.env` resolve
to the repo root. To pull the published image instead of building locally, set
`image: ghcr.io/erikthorsell/feed2epub:<tag>` and drop the `build:` key.
