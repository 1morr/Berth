# Upgrading

For anyone running Berth who wants a newer version, wants to stay on one version, or wants to run an image they
built themselves.

## Versions and image tags

The compose file pulls `ghcr.io/1morr/berth:latest`, which is always the newest stable release. Each release also
has `:<version>` (e.g. `:0.2.0`) and `:<major>.<minor>` (`:0.2`) tags; to stay on one, change the `berth` image in
`docker-compose.yml` to it. Pre-releases (`-rc1` and so on) only get `:<version>` and never move `:latest`.

The deployment files are attached to every release, twice with the same contents: `berth-deploy-<version>.zip`
and `berth-deploy.zip`.
`https://github.com/1morr/Berth/releases/latest/download/berth-deploy.zip` is always the newest stable release;
a given version is at `https://github.com/1morr/Berth/releases/download/v<version>/berth-deploy-<version>.zip`.
Pre-releases have the attachments too, but they are marked as pre-releases, so the `latest` link never points at
one.

## Upgrade steps

Upgrade the compose file along with the image. It changes between versions (container names, the pinned Jellyfin
tag, variables in `.env`); pulling a new image alone leaves you with the old file.

1. Download that version's zip and unzip it over your existing `berth/`: `docker-compose.yml` and `preseed/` are
   replaced. Compare the new `.env.example` with your `.env` and copy any new variables across (`.env` itself is
   not in the zip and is never overwritten).
2. `docker compose pull && docker compose up -d`. Berth applies database migrations on start.

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
