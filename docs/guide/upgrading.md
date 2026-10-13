# Upgrading

For anyone running Berth who wants a newer version, wants to stay on one version, or wants to run an image they
built themselves.

## Versions and image tags

The compose file pulls `ghcr.io/1morr/berth:latest`, which is always the newest stable release. Each release also
has `:<version>` (e.g. `:0.2.0`) and `:<major>.<minor>` (`:0.2`) tags; to stay on one, change the `berth` image in
`docker-compose.yml` to it. Pre-releases (`-rc1` and so on) only get `:<version>` and never move `:latest`.

The deployment is two files attached to every release: `docker-compose.yml` and `example.env` (the repo's
`deploy/docker-compose.yml` and `deploy/.env.example` at that release's tag). The links in the README,
`https://github.com/1morr/Berth/releases/latest/download/docker-compose.yml` and `.../example.env`, always give the
newest stable release's. To stay on one version, replace `latest/download` with `download/v<version>`:
`https://github.com/1morr/Berth/releases/download/v<version>/docker-compose.yml` (and `example.env`). Releases before
0.2.4 have no attachments; take their files from the tag,
`https://raw.githubusercontent.com/1morr/Berth/v<version>/deploy/docker-compose.yml` (and `.env.example`). Use the
files of the version you run, not the ones on `main`: `main` can be ahead of the image.

## Upgrade steps

Upgrade the compose file along with the image. It changes between versions (container names, the pinned Jellyfin
tag, the whitelist script inside it, variables in `.env`); pulling a new image alone leaves you with the old file.

1. Replace your `docker-compose.yml` with that version's whole file (on Unraid: **Edit Stack → Compose File**, paste
   over everything). Compare that version's `example.env` with your `.env` and copy any new variables across; your
   `.env` is never replaced.
2. `docker compose pull && docker compose up -d` (Unraid: the stack's **Update Stack**). Berth applies
   database migrations on start.

What changed in each version, and what to watch for when upgrading: [CHANGELOG.md](../../CHANGELOG.md).

## Bundled Jellyfin

The bundled Jellyfin is pinned to one minor line (`version-12.1ubu2604`), so `docker compose pull` gets its
rebuilds but not the next version. To move it on: back up `${CONFIG_ROOT}/jellyfin`, change the tag in
`docker-compose.yml`, then `docker compose up -d jellyfin`. Moving from Jellyfin 10.x to 12 has its own steps; see
[Requirements](requirements.md#service-versions).

## Building your own image

To run changes that are not released yet, build an image from the repo root under the tag the compose file uses:

```bash
docker build -f deploy/Dockerfile -t ghcr.io/1morr/berth:latest .
```

The next `docker compose pull` replaces it with the version on GHCR. Releases are pushed to GHCR by
`.github/workflows/release.yml` on `v*` tags.
