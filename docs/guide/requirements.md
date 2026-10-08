# Requirements

For anyone choosing where to put `DATA_ROOT`, which host to run Berth on, or checking that an existing Jellyfin,
qBittorrent or Prowlarr is new enough.

## Docker

Docker Engine or Docker Desktop with Compose v2 (`docker compose`; the old `docker-compose` v1 cannot read the
compose file). The host must reach `ghcr.io` and `lscr.io` to pull images, and `api.themoviedb.org` for TMDB.

One host runs one Berth stack: the project name, container names, network and subnet are fixed in the compose
file, so a second copy on the same host (say, one for real use and one to try things) clashes and does not start.

## Hardlinks

Berth imports by hardlinking, not copying: the file qBittorrent seeds and the file Jellyfin plays are the same
file on disk, so an import takes no extra space. That needs:

- **One media root.** The download folders and the libraries all live under `DATA_ROOT`, and the containers that
  touch files (Berth, qBittorrent, Jellyfin) mount that one folder at `/data`. Splitting downloads and libraries
  into two bind mounts gives `EXDEV`, and the Route check on wizard page 3 stops there.
- **A filesystem that supports hardlinks.** Not exFAT. Not across btrfs subvolumes, ZFS datasets or mergerfs
  branches either: to the kernel those are different devices. Network shares (SMB / NFS) are not supported.
  Unraid user shares (`/mnt/user/...`) are shfs, not mergerfs, and hardlinks work there; see [Unraid](#unraid).
- **One machine.** Berth and qBittorrent must see the same files. Other hosts and remote path mapping are not
  supported.

With a clone of the repo you can check a folder before installing: `sh scripts/experiments/hardlink.sh
/path/to/folder` prints PASS or EXDEV. Without one, wizard page 3 runs the same check.

## Host platforms

Tested end to end: Windows with Docker Desktop (an NTFS bind mount, and ext4 inside Docker Desktop's Linux VM)
and Unraid 7.1.4 on a user share. **Other Linux distributions and NAS systems have not been tested yet.** They
should work the same way, but nobody has run them.

### Linux

`DATA_ROOT` must be writable by `PUID` / `PGID`, e.g. `chown -R 1000:1000 /srv/berth/data`. Berth only takes
ownership of the media root when it is still empty; it never touches a folder that already has content.

### Windows (Docker Desktop, WSL 2 backend)

Use a plain bind mount (`DATA_ROOT=C:\Berth\data`); no named volume is needed. Hardlinks on NTFS work. `PUID` /
`PGID` mean nothing on these mounts; leave the defaults.

### Unraid

Tested on 7.1.4. Install the **Compose Manager** plugin first; it provides `docker compose`.

- Rename the `berth/` folder from the zip and put it at `/mnt/user/appdata/berth-deploy/` (not `appdata/berth`,
  which is where `CONFIG_ROOT` goes below). Run `cp .env.example .env` and `docker compose up -d` there.
  **Don't keep it on the USB flash drive**: Compose Manager stores stacks under
  `/boot/config/plugins/compose.manager/projects/` by default, which is vfat, cannot run scripts, and would put
  `./data` and `./config` on the flash drive too. To manage it from Compose Manager's page: **Add New Stack**,
  name it `berth`, and set **Indirect Path** under the advanced fields to `/mnt/user/appdata/berth-deploy`
  (worked out from the plugin's source; not clicked through in testing).
- `.env`: `PUID=99`, `PGID=100` (Unraid's `nobody:users`), `DATA_ROOT=/mnt/user/<share>/Berth`,
  `CONFIG_ROOT=/mnt/user/appdata/berth`. You don't need to create either folder. On a server that already runs
  Emby or Jellyfin and qBittorrent, 8096, 8080 and 6881 are usually taken; change `JELLYFIN_PORT`,
  `QBITTORRENT_WEBUI_PORT` and `QBITTORRENT_BT_PORT`.
- Hardlinks: **Settings → Global Share Settings → Tunable (support Hard Links)** must be **Yes**, and all of
  `DATA_ROOT` must be in one share. If the share uses a cache pool, the mover moves both names to the array
  together and the hardlink survives (tested). The mover skips files being read for seeding and moves them on a
  later run.
- Files are `644` and folders `755` (`UMASK=022`): visible over SMB but read-only. Set `UMASK=000` to edit or
  delete them over SMB.
- Existing services on the same server: `http://host.docker.internal:<port>` (it resolved to docker0's
  `172.17.0.1` in testing). To add the `/data` mount to an existing container, see
  [Unraid templates](existing-services.md#unraid-templates).

## Service versions

- **qBittorrent 4.4 or newer** (Web API 2.8.4). The bundled container gets an address whitelist from
  `preseed/qbittorrent/10-berth.sh` before it starts, and it lets in only Berth's fixed IP. Since 4.6.1 the
  first-run random password is printed only in the container log, so without this step Berth cannot get in. The web
  UI still needs a password from the host or your LAN. Berth writes none of the global preferences (default save
  path, automatic torrent management, incomplete folder): each torrent it sends uses automatic management in a
  `berth-*` category that carries its own save path and incomplete folder (`/data/torrent/incomplete/<slug>`). The
  script never overwrites a setting that already has a value.
- **Jellyfin 12.0 or newer** (12.0 is what used to be 10.12; Jellyfin dropped the leading `10`). From 12.0,
  Jellyfin itself merges several versions of one episode into one item, with no plugin. On 10.x that needed a
  third-party plugin, which does nothing on 12 and merges across libraries by mistake, so Berth supports 12 and
  later only. An older server is red on the wizard's Jellyfin page and on the health page and is not connected.
  - **Upgrading from 10.x**: 10.10.7 and any 10.11.x can go straight to 12. **Before**: back up Jellyfin's config
    folder completely (`${CONFIG_ROOT}/jellyfin` for the bundled one) — 12 changes the database and cannot be
    downgraded, only restored — and remove third-party plugins, since 10.11 plugins don't load on 12. **After**:
    run a full library scan so automatically grouped versions come back.
  - **The bundled Jellyfin is pinned to `version-12.1ubu2604`**, so `docker compose pull` only brings rebuilds
    of 12.1 and never jumps to the next major version silently. See [Upgrading](upgrading.md#bundled-jellyfin).
- **Prowlarr 1.3.2 or newer** (the newest endpoint Berth uses is the anonymous `/ping`). Older ones are red on the
  wizard's Prowlarr page and the health page. The bundled Prowlarr gets nothing preseeded: Berth mounts its config
  folder read-only to read the API key Prowlarr generates.
- **TMDB**: your own API key (see the [README](../../README.md#what-you-need)); Berth ships none. It is stored in
  Berth's database; change it on the wizard's TMDB page or under **Settings → TMDB**. A new key replaces the old
  one only after it passes the test; if it fails, the old one stays in use. TMDB's terms allow non-commercial use
  only.
