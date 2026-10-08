# Berth

**English** · [繁體中文](README.zh-Hant.md)

Self-hosted media acquisition that ends in your Jellyfin library. Find a release through Prowlarr or follow an
RSS feed; Berth sends it to qBittorrent, works out which film or episode each file is (from TMDB), and hardlinks it
into Jellyfin under a name Jellyfin recognises. It keeps a ledger of every file it placed, so it can check and
repair the library later.

| | |
| --- | --- |
| ![The setup wizard checking library paths](docs/assets/screenshots/wizard.png) | ![Searching for a release on a title page](docs/assets/screenshots/title-search.png) |
| ![A Jellyfin library browsed in Berth](docs/assets/screenshots/library.png) | ![The health page](docs/assets/screenshots/health.png) |

Berth is a public beta. Read [Status & known limitations](#status--known-limitations) before relying on it.

## What you need

- Docker Engine or Docker Desktop with Compose v2 (`docker compose`, not `docker-compose`).
- A folder for downloads and media on one local disk that supports hardlinks: not exFAT, not a network share.
  Details in [Requirements](docs/guide/requirements.md).
- **A free TMDB API key. Get it first**; it takes about five minutes:
  1. Sign up at <https://www.themoviedb.org/signup> and confirm the email.
  2. Open <https://www.themoviedb.org/settings/api> and request an API key; choose **Personal / Education**.
     It is issued immediately.
  3. Keep either the **API Key** or the **API Read Access Token**; Berth accepts both.

## Install

1. Download [`berth-deploy.zip`](https://github.com/1morr/Berth/releases/latest/download/berth-deploy.zip) and
   unzip it. You get a `berth/` folder with `docker-compose.yml`, `.env.example` and `preseed/`. Keep them
   together: without `preseed/`, Berth cannot get into the bundled qBittorrent.

   ```bash
   curl -LO https://github.com/1morr/Berth/releases/latest/download/berth-deploy.zip
   unzip berth-deploy.zip && cd berth
   cp .env.example .env
   ```

2. Edit `.env`:
   - `DATA_ROOT`: where downloads and the libraries live. The default `./data` is fine for a trial; for real
     use, point it at your media disk (`/srv/berth/data`, `C:\Berth\data`).
   - `PUID` / `PGID`: the account that owns `DATA_ROOT` (`id -u` / `id -g`; Unraid: `99` / `100`). Leave them on
     Docker Desktop for Windows.
   - `TZ`: your time zone, e.g. `Europe/London`.
   - Already running Jellyfin, qBittorrent or Prowlarr? Remove it from `COMPOSE_PROFILES` to connect yours, or
     change its `*_PORT` to run both. Otherwise `up -d` stops at `port is already allocated`. See
     [Connecting services you already run](docs/guide/existing-services.md).

3. Start it, and wait until `berth` shows `(healthy)` (about a minute on the first pull):

   ```bash
   docker compose up -d
   docker compose ps
   ```

4. Open <http://localhost:8383> and follow the wizard.

## The setup wizard

Six pages. On the Jellyfin, qBittorrent and Prowlarr pages you first choose **Bundled** (started by this compose
file) or **Existing** (one you already run); Berth tests each choice on the spot.

1. **Jellyfin**: create the Jellyfin admin, or sign in as one. This account is also how you sign in to Berth.
2. **qBittorrent**: set its web UI login, or enter your existing one's address and login.
3. **Library paths**: each library gets a *Route* (the path from download to library), and Berth proves with
   a real file that hardlinks work. Bundled Jellyfin starts with Movies, TV and Anime; with your own, you tick
   which libraries Berth may write to.
4. **Prowlarr**: add the recommended public indexers with one press, or use your own. You can skip this.
5. **TMDB**: paste your key. It must pass the test.
6. **Finish**: what you skipped and where to finish it.

Page by page, with what Berth changes in each service: [Setup wizard](docs/guide/setup-wizard.md).
Back up `${CONFIG_ROOT}/berth` (`./config/berth` by default); that folder is everything Berth knows.

## Status & known limitations

Berth is a **public beta**.

- It works with **Jellyfin 12.0 or newer** and **Prowlarr** only. No Emby, Plex or Jackett.
- No notifications yet: open Berth to see what needs you.
- Tested end to end on **Windows with Docker Desktop** and on **Unraid 7.1**. Other Linux distributions and NAS
  systems have not been tested yet.
- **Don't expose Berth directly to the internet.** Reach it over your LAN or a VPN.
- Known issues (tracking notes, in Chinese):
  - Without Prowlarr (skipped in the wizard or removed later) the health page stays red; there is no "don't use
    Prowlarr" option yet ([61](.scratch/m4/issues/61-prowlarr-optional.md)).
  - When a new import does not show up, Berth asks Jellyfin to scan every library, not only its own, and the first
    import into an empty library can take over ten minutes to show as found
    ([62](.scratch/m4/issues/62-jellyfin-scan-scope.md)).
  - When an existing service lacks the `/data` mount, the fix shown says `${DATA_ROOT}:/data` instead of your
    actual folder, and Jellyfin's mount is only checked on page 3
    ([63](.scratch/m4/issues/63-copyable-mount-remedies.md)).
  - An existing Jellyfin needs a library of each type you want; Berth adds a path to it but does not create one
    ([64](.scratch/m4/issues/64-new-library-on-existing-jellyfin.md)).
  - After switching to another qBittorrent, torrents still seeding on the old one stay there untracked, and Berth
    does not say so ([65](.scratch/m4/issues/65-switch-explains-what-stays.md)).
- Fixed since the last audit:
  - Switching qBittorrent rechecks every Route by itself, and the health page no longer shows unchecked Routes as
    green ([59](.scratch/m4/issues/59-health-tells-the-truth-after-switch.md)).
  - After a reinstall or a lost database, the wizard's last page and **Issues** offer to rebuild the ledger from
    the library ([60](.scratch/m4/issues/60-rebuild-ledger-from-the-ui.md)).

## Guides

- [Setup wizard](docs/guide/setup-wizard.md): each page in detail, accounts and passwords, the pages after setup.
- [Connecting services you already run](docs/guide/existing-services.md): the `/data` mount (Compose,
  `docker run`, Unraid templates), `COMPOSE_PROFILES`, switching servers.
- [Requirements](docs/guide/requirements.md): hardlinks, Linux / Windows / Unraid, minimum service versions.
- [Upgrading](docs/guide/upgrading.md): image tags, upgrade steps, building your own image.
- [Troubleshooting](docs/guide/troubleshooting.md): ports, `Unauthorized`, `host.docker.internal`.
- [Backup, secrets and reinstalling](docs/guide/backup-and-reinstall.md): what Berth stores, starting over,
  rebuilding the ledger.
- [CHANGELOG](CHANGELOG.md): what changed in each version.
- [Development](docs/development.md) (in Chinese): building, testing and the project layout.

## License and attribution

MIT, see [LICENSE](LICENSE).

<img src="docs/assets/tmdb.svg" alt="TMDB" height="28">

This product uses the TMDB API but is not endorsed or certified by TMDB. TMDB's terms allow non-commercial use
only.
