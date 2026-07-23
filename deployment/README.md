# Deploying feed2epub

feed2epub is two cooperating processes over a shared library folder — a **fetcher** (rebuilds the daily EPUBs
and prunes old ones) and an OPDS **server** (publishes that folder). Both run from the same image; only the
command differs. Two supported targets:

| Target | Directory | Use it when |
|---|---|---|
| Docker Compose | [`docker-compose/`](docker-compose/) | A single host with Docker; simplest. Builds the image locally. |
| Kubernetes | [`kubernetes/`](kubernetes/) | A cluster. Pulls the published image from GHCR. |

Both need the same two pieces of **deployment configuration**, which are *not* in the image and *not* tracked
in Git:

1. **`feeds.yaml`** — your feed list. Copy [`../feeds.example.yaml`](../feeds.example.yaml) and edit it.
2. **`INSTAPAPER_FEED_URL`** (optional) — only if a feed's URL references `${INSTAPAPER_FEED_URL}` (or any
   `${VAR}`); the app fails config-load if a referenced variable is unset. Compose reads it from `.env`;
   Kubernetes from a Secret.

The image is published to `ghcr.io/erikthorsell/feed2epub` by [`.github/workflows/publish.yaml`](../.github/workflows/publish.yaml)
on each `v*.*.*` git tag.
