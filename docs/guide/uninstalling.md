# Uninstalling Berth

For anyone who is done with Berth and wants their services back to how they were before it, and the disk space
its downloads use.

Berth has no "uninstall" button. Everything it made in your services is listed below, with where to remove it.
None of it is needed by anything except Berth, and removing it leaves the rest of your setup alone.

## The short way: bundled services you no longer need

If you chose **Bundled** for a service and don't want to keep that service either, there is nothing to clean up
inside it: stop the stack and delete its folder.

```bash
docker compose down
```

This stops and removes Berth and every bundled container in the compose file. Their settings are in
`${CONFIG_ROOT}/<service>` (`berth`, `jellyfin`, `qbittorrent`, `prowlarr`); delete the folders you don't want.
Your downloads and libraries are in `DATA_ROOT`, see [Disk space and hardlinks](#disk-space-and-hardlinks).

To keep a bundled service (say the Jellyfin, with your watch history), keep its folder and clean it up like an
existing one below. Bundled services also have a login Berth set up for you; change it in that service if you
like.

## Before you stop Berth

Two things are easier to find while Berth still runs:

- **Which Prowlarr indexers Berth added.** Prowlarr itself doesn't show who added a site. On a bundled Prowlarr,
  **Settings → Prowlarr** offers **Remove** only on the sites Berth added; remove them there. On an existing
  Prowlarr, choose **Bundled** on that page: before anything changes, the confirmation lists the sites Berth
  added. Note them and cancel. Sites added before Berth 0.2.0 were not recorded and are not listed.
  If you chose **Stop using Prowlarr**, that page lists no sites; press **Use Prowlarr again** first.
- **Which torrents are Berth's.** Every torrent Berth sends has the tag `berth` and a `berth-*` category; filter
  on either in qBittorrent.

## Jellyfin

In Jellyfin's dashboard:

- **API keys**: delete the key named "Berth".
- **Devices**: delete the "Berth" devices, one for each person who signed in to Berth.
- **Libraries**: each of your own libraries that Berth uses has one extra folder, `/data/library/<name>`.
  Remove that folder from the library; your own folders stay. Jellyfin drops the items in it on its next scan.
- Libraries Berth created (the bundled ones, or the one you ticked on wizard page 3): delete them or keep them.

Berth never changed your existing server's name, users or settings. The only exception: if Berth ran a fresh
server's first-time wizard, the admin, language and remote access setting came from that, and stay as they are.

## qBittorrent

1. **Stop Berth first.** Berth recreates a deleted `berth-*` category the next time it sends a torrent or checks
   a library path.
2. Remove the torrents tagged `berth`. Whether to delete their files too: see
   [Disk space and hardlinks](#disk-space-and-hardlinks).
3. Delete the `berth-*` categories.

Berth never changed qBittorrent's global preferences (default save path, temp path, automatic torrent
management), so there is nothing to undo there.

A bundled qBittorrent also has its web UI login, and a whitelist that lets Berth in without a password:
`WebUI\AuthSubnetWhitelistEnabled` and `WebUI\AuthSubnetWhitelist` in
`${CONFIG_ROOT}/qbittorrent/qBittorrent/qBittorrent.conf`. Stop qBittorrent before editing that file, or turn
the whitelist off under **Options → WebUI → Bypass authentication for clients in whitelisted IP subnets**.

## Prowlarr

Delete the indexers Berth added ([listed while Berth runs](#before-you-stop-berth)). Berth never removed or
changed your own indexers, and never set the login of an existing Prowlarr. A bundled Prowlarr has the web UI
login Berth set; change it under **Settings → General → Security**.

## Disk space and hardlinks

Berth's files are under `DATA_ROOT`:

- `torrent/complete` and `torrent/incomplete`: what qBittorrent downloaded, one folder per library path.
- `library`: the files Jellyfin shows, one folder per library path.

A file in `library` is a **hardlink** to the download in `torrent/complete`: one copy of the data with two
names. Deleting one name frees nothing; the space comes back when both are gone. So to free the space, delete the
download (or remove the torrent together with its files) **and** the library file. To keep watching in Jellyfin
without Berth, keep the `library` folders and delete only `torrent`; the files stay playable.

If Berth stopped in the middle of a check, a probe file named `.berth-probe-…` may be left at the top of
`DATA_ROOT` or in one of Berth's folders under it, and a stopped probe torrent of the same name in qBittorrent;
delete them.

## Berth itself

`docker compose down` (above) stops Berth along with the bundled services. To stop only Berth and keep the
bundled services running:

```bash
docker compose stop berth
docker compose rm berth
```

Remove `berth` from the compose file too, or the next `docker compose up -d` starts it again.

Berth's database, `${CONFIG_ROOT}/berth`, holds the services' API keys and your TMDB key. Delete it, or keep it
in case you come back: see [Backup, secrets and reinstalling](backup-and-reinstall.md).
