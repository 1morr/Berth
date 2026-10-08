# Connecting services you already run

For people who already run Jellyfin, qBittorrent or Prowlarr and want Berth to use those instead of the bundled
ones. If you start from nothing, you can skip this page: choose **Bundled** on every wizard page.

## Before `docker compose up -d`

Every service you will connect as **Existing** comes out of `COMPOSE_PROFILES` in Berth's `.env`, so the bundled
one does not start. `berth` itself has no profile and always starts.

```dotenv
COMPOSE_PROFILES=qbittorrent,prowlarr   # use your own Jellyfin
COMPOSE_PROFILES=                       # use your own Jellyfin, qBittorrent and Prowlarr
```

If you leave it in, the bundled one tries to publish the same port as yours and stops at
`port is already allocated` (Berth and the other services still start). To run the bundled one next to yours
instead, change its `*_PORT` in `.env`. Container names are `berth-jellyfin`, `berth-qbittorrent` and
`berth-prowlarr`, so they never clash with a container called `jellyfin`.

## What an existing service needs

For Jellyfin and qBittorrent (Prowlarr only needs to be reachable):

- **The same host as Berth**, with Berth's `DATA_ROOT` mounted at container path **`/data`** — exactly `/data`.
  Berth's download and library folders are fixed under it (`/data/torrent/...`, `/data/library/...`) and there is
  no setting to change that. There is no remote path mapping, so a server on another NAS cannot be connected.
- **Your existing mounts stay as they are; add this one.** Berth reads and writes only under `/data`.
  qBittorrent keeps its `/downloads` and old torrents keep seeding; Jellyfin keeps `/tv` and `/movies` (changing
  an existing library path makes Jellyfin treat everything as new items and resets watch history). On page 3
  Berth adds a `/data/library/<folder>` path to each library you tick.
- `DATA_ROOT` must be on a filesystem that supports hardlinks (see [Requirements](requirements.md#hardlinks)).
  Your existing media folders don't need to be on the same filesystem; hardlinks only happen inside `DATA_ROOT`.
- An existing Jellyfin must already have a library of each type you want (films, shows). Berth adds a path to
  it but does not create libraries on an existing server.

### Docker Compose

Example: media at `/volume1/media` and downloads at `/volume1/downloads` on a NAS, and Berth's `.env` has
`DATA_ROOT=/volume1/berth`. Use the absolute path: a relative one like `./data` means a different folder in a
different compose file.

```yaml
# your own compose file: one extra line per service, nothing else changes
services:
  jellyfin:
    volumes:
      - /volume1/docker/jellyfin:/config
      - /volume1/media/tv:/tv            # existing, keep it
      - /volume1/berth:/data             # new: the same host folder as Berth's DATA_ROOT
  qbittorrent:
    volumes:
      - /volume1/docker/qbittorrent:/config
      - /volume1/downloads:/downloads    # existing, keep it (old torrents keep seeding)
      - /volume1/berth:/data             # new
```

Then recreate the containers: `docker compose up -d` recreates the ones whose `volumes` changed.

### `docker run`

Add `-v /volume1/berth:/data` to the command you used, remove the container, and run the new command.

### Unraid templates

On Unraid's **Docker** tab, click the container → **Edit**, then at the bottom **Add another Path, Port,
Variable, Label or Device**:

- **Config Type**: Path
- **Container Path**: `/data`
- **Host Path**: the same folder as Berth's `DATA_ROOT`, e.g. `/mnt/user/<share>/Berth`
- **Access Mode**: Read/Write

Press **Add**, then **Apply**; Unraid recreates the container. Field names are from the
[Unraid docs](https://docs.unraid.net/unraid-os/using-unraid-to/run-docker-containers/managing-and-customizing-containers).

Some templates already mount media under `/data` (the Jellyfin template from Community Apps uses `/data/tvshows`
and `/data/movies`). Adding `/data` on top makes those nested mounts. Berth only uses `/data/torrent` and
`/data/library`, so it should work, but this has not been tested.

If a mount is missing, the wizard's check fails on that service and shows the same fix: qBittorrent on page 2,
Jellyfin on page 3.

## Prowlarr

An existing Prowlarr needs its address and API key (**Settings → General → Security** in Prowlarr). If you
deploy Prowlarr with the `PROWLARR__AUTH__APIKEY` environment variable, you can give Berth the same variable
instead of mounting Prowlarr's config folder read-only; when set, it wins over `config.xml`.

## Addresses: `host.docker.internal`, not `localhost`

Berth runs in a container, so `localhost` is Berth itself. For a service on the same host use
`http://host.docker.internal:<port>`. Docker Desktop provides that name; on Linux the compose file adds it to
`berth` (`extra_hosts: host.docker.internal:host-gateway`, which resolves to `172.17.0.1` on Unraid). On Linux the
service must also listen on `0.0.0.0`; one that only listens on `127.0.0.1` cannot be reached from a container.
Check that the name resolves:

```bash
docker compose exec berth getent hosts host.docker.internal
```

## Stopping a bundled service you no longer use

Removing a service from `COMPOSE_PROFILES` and running `docker compose up -d` does **not** stop a bundled container
that is already running (Compose leaves services outside the active profiles alone, and `--remove-orphans` does
not count them). Two steps:

1. Remove the services you chose **Existing** for from `COMPOSE_PROFILES` in `.env` (the wizard page prints the
   whole line for your choices, e.g. `COMPOSE_PROFILES=prowlarr`), so later `up -d` runs don't start them.
2. Stop the ones already running (the wizard page prints this line too). Stopped services are not started again by
   later `up -d` runs:

   ```bash
   docker compose stop jellyfin qbittorrent
   ```

Forgetting is harmless: the bundled container keeps running under its `berth-*` name and only wastes resources.

The other way round: when the bundled service is not running (its host name does not resolve; Berth only looks
the name up on page load and after each test, it does not connect), its **Bundled** card says so. A stopped
container and one missing from `COMPOSE_PROFILES` look the same, so both fixes are given:
`docker compose start <service>`, or add it back to `COMPOSE_PROFILES` and `up -d`. After that, or after changing a
port in `.env`, **choose Bundled again** on that page: it saves the compose address again and tests it. **Test
again** only retries the address already saved.

## Switching to another server later

- **Jellyfin** is locked once there is an owner: the owner is an account on that server, so another server means
  another owner. After the wizard, change the address under **Settings → Jellyfin**.
- **qBittorrent and Prowlarr** can be switched at any time. What Berth already wrote into the old one stays
  there and is not undone; that page has to be done again. When you switch qBittorrent, Berth rechecks every Route
  on its own. Torrents still seeding on the old qBittorrent stay there and Berth stops tracking them.
