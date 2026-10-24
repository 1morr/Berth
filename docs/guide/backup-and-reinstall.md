# Backup, secrets and reinstalling

For anyone who wants to know what Berth stores and how to back it up, or who has to start the wizard over or
recover after losing Berth's database.

## What Berth stores, and backing it up

Everything Berth knows is in `${CONFIG_ROOT}/berth/berth.db`: the services' API keys, your TMDB key, the
download history, review and issue state, and the *ledger* (the record of which library file came from which
download). Secrets are protected by file permissions only, with no application-level encryption (the same as
Seerr). Berth never stores your Jellyfin password in plain text; see
[Accounts and passwords](setup-wizard.md#accounts-and-passwords). Berth's logs, and the errors it reports when
a service or feed cannot be reached, show URLs with every query value replaced by `***` (for example a Mikan
feed's `token=***`), so a log you paste somewhere does not carry your feed token or API keys.

**To back up Berth, copy `${CONFIG_ROOT}/berth`.** Back up the other folders under `CONFIG_ROOT` (`jellyfin`,
`qbittorrent`, `prowlarr`) if you want those services' settings too. Your media is in `DATA_ROOT` and is not part
of this.

## Rerunning the wizard

The wizard is only for the first time. After it, opening `/setup` takes you to **Settings → Jellyfin**, which says
the wizard is done; switching services and changing addresses and logins all happen in Settings.

To really start over (or when the database is damaged or lost): stop Berth, move `${CONFIG_ROOT}/berth` away
(don't delete it; keep it as a backup), then `docker compose up -d`.

- **The three services' settings stay.** Jellyfin's, qBittorrent's and Prowlarr's config folders are untouched.
  Each wizard page runs again but creates nothing twice (the API key, libraries, categories and indexers are all
  idempotent). Page 1 becomes "sign in as your Jellyfin admin", and on page 3 you press **Build and check**
  yourself.
- **Paste the TMDB key again**: it was in the database you moved away.
- **Download history, past downloads, review and issues are empty**: they were in that database too.
- **The ledger comes back by rebuilding it.** The files in your libraries are all still there, but Berth no longer
  knows them. The wizard's last page and the top of **Issues** say how many library files are missing from the
  ledger; press **Rebuild the ledger from the library** and they come back. Torrents still seeding in qBittorrent
  show up as unclaimed torrents: after the rebuild, use **Claim it as a download** and the files already in the
  library rejoin their original row.

## What a ledger rebuild does

For each Route, Berth walks the library, and for every file the ledger does not know:

- if a file in `complete` has **the same inode**, and the library path reads back as a season, episode and tags
  under Berth's naming template (Berth recomputes the name and requires an exact match), the full ledger row comes
  back;
- anything that does not match is **never guessed**: it becomes an *unmanaged library file* issue with the reason
  on it (outside every Route, no source in `complete`, unknown title, not Berth's naming). See them under
  **Issues**. A file that was already judged (an open issue with a reason, or one you ignored) is not counted
  again.

It **only adds**: it deletes nothing, and leaves ledger rows whose file is gone alone (the nightly check reports
those). It can run while Berth is running and is safe to repeat. While the nightly check is running, the button is
refused; press it again once the check is done.

The same command from a shell:

```bash
docker compose exec berth berth rebuild-ledger
```

It prints counts. If a Route's target folder cannot be read, that Route is skipped and listed, and the exit code
is 1. If a folder under `complete` cannot be read, the exit code is also 1, and files without a source in that run
are counted as `not decided` rather than reported as having no source.

For a single file, the same thing is **Claim it into the ledger** on that file's row under **Issues**.
