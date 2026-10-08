# Troubleshooting

For when Berth or one of its services does not start, cannot be reached, or the wizard cannot connect.

## Is it up?

```bash
docker compose ps              # berth should show (healthy); the first pull takes a minute or so
docker compose logs berth      # what Berth printed while starting
```

The image has no `curl`. To test an external service from Berth's side:

```bash
docker compose exec berth python -c \
  "import urllib.request; print(urllib.request.urlopen('http://qbittorrent:8080/api/v2/app/version').read())"
```

(Replace 8080 with your `QBITTORRENT_WEBUI_PORT`.)

## Ports

| Service | `.env` variable (default) | Notes |
| --- | --- | --- |
| Berth | `BERTH_PORT` (8383) | The only interface you need. |
| qBittorrent | `QBITTORRENT_WEBUI_PORT` (8080), `QBITTORRENT_BT_PORT` (6881) | The web UI asks for the login you set on wizard page 2 when opened from the host or LAN (change it under **Settings → qBittorrent → Interface login**). Both ports are the same number inside and outside the container. |
| Jellyfin | `JELLYFIN_PORT` (8096) | **Open in Jellyfin** opens this port. |
| Prowlarr | `PROWLARR_PORT` (9696) | |

When a port clashes with something else on the machine, change these variables in `.env` and run
`docker compose up -d`. **Don't edit the compose file.** `.env` holds only these host-side facts that Berth
cannot see from inside its container; service addresses and credentials, download folders and library paths are
all changed in the wizard and in Settings.

**Settle `QBITTORRENT_WEBUI_PORT` before running the wizard.** Berth saves the address of the bundled
qBittorrent at the moment you choose **Bundled** on page 2; changing the variable later does not follow it.
Choosing **Bundled** on page 2 again saves it again.

## `port is already allocated` on `docker compose up -d`

Something on the host already uses that port — usually your own Jellyfin, qBittorrent or Prowlarr while
`COMPOSE_PROFILES` in `.env` still includes the bundled one. Only the clashing container fails (it stays
`created`); Berth and the others run. To use yours: choose **Existing** on that wizard page, remove it from
`COMPOSE_PROFILES` and `docker compose up -d`. To use the bundled one: change that service's `*_PORT` in `.env`.
See [Connecting services you already run](existing-services.md).

## qBittorrent's web UI says `Unauthorized`

Change `QBITTORRENT_WEBUI_PORT`; don't edit the compose file. qBittorrent's Host header check compares the port as
well as the domain, and even `WebUI\ServerDomains=*` rejects a request whose port does not match. If you change
the published port in the compose file to something like `18080:8080`, `http://localhost:18080` only shows
`Unauthorized`, and the real reason (`Invalid Host header, port mismatch`) is only in
`docker compose logs qbittorrent`. `QBITTORRENT_WEBUI_PORT` changes both sides and qBittorrent's own `WEBUI_PORT`
to the same number. **Don't** turn off `WebUI\HostHeaderValidation`: it is qBittorrent's protection against DNS
rebinding.

## Berth cannot reach a service on the host

Use `host.docker.internal` as the address, not `localhost`: inside Berth's container `localhost` is Berth itself.
Docker Desktop provides that name; on Linux the compose file adds it to `berth` with
`extra_hosts: host.docker.internal:host-gateway`. On Linux the service must also listen on `0.0.0.0`; one listening
only on `127.0.0.1` cannot be reached from a container. Check that the name resolves:

```bash
docker compose exec berth getent hosts host.docker.internal
```

## The wizard says the bundled service is not running

Its host name does not resolve on the compose network: the container is stopped, or it is not in
`COMPOSE_PROFILES`. Run `docker compose start <service>`, or add it back to `COMPOSE_PROFILES` and
`docker compose up -d`; then choose **Bundled** on that page again. Details in
[Connecting services you already run](existing-services.md#stopping-a-bundled-service-you-no-longer-use).

## A check on wizard page 3 is red

The message names the container and the missing mount. The usual causes: an existing service without the `/data`
mount ([fix](existing-services.md#what-an-existing-service-needs)), or `DATA_ROOT` on a filesystem without
hardlinks ([requirements](requirements.md#hardlinks)).

## The TMDB key does not pass

The TMDB page really calls TMDB to check the key. If the key is right, check that the machine can reach
`api.themoviedb.org`; a firewall blocking it stops the wizard on page 5.

## A file I copied into a library folder does not show up in Jellyfin

The libraries Berth creates in the bundled Jellyfin have real-time monitoring turned off, on purpose: Berth tells
Jellyfin about every file it imports. Files you drop into those folders yourself appear after Jellyfin's next
scheduled library scan, or when you scan the library from Jellyfin's dashboard.
