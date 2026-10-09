# Setup wizard

For anyone going through Berth's first-run wizard who wants to know what each page does before pressing it,
or what to do after it. The short version is in the [README](../../README.md#the-setup-wizard).

## How the wizard works

Open `http://localhost:8383` (or your `BERTH_PORT`) after `docker compose up -d`. Everything is set up from
there; you don't need to open the other three services' interfaces. The exceptions are private indexers (you add
those in Prowlarr's own interface) and existing services that are missing a mount (you edit their compose file or
template, see [Connecting services you already run](existing-services.md)).

Six pages, five berths. The board at the top shows them as BTH 1–5: Jellyfin, qBittorrent, Library paths,
Prowlarr, TMDB, then the finish page.

**Jellyfin, qBittorrent and Prowlarr each start with a choice**: **Bundled** (the one this compose file
started) or **Existing** (one you already run). Nothing is pre-selected and nothing is guessed: Berth connects
only after you choose, and tests the choice on the spot.

| Berth | Page | Bundled | Existing |
| --- | --- | --- | --- |
| BTH 1 | 1 Jellyfin | Connects to the bundled server. While it is still starting, the page counts down and retests every 3 seconds on its own (for up to 2 minutes). | Enter its address and press **Test connection**. |
| | | If that server has not run its own first-time wizard, Berth creates the admin with the username and password you enter and finishes Jellyfin's initial setup; if it already has an admin, you sign in as that admin. Either way Berth creates an API key named "Berth" on it. | After the test, sign in as its admin. Berth creates an API key named "Berth". If it has not run its first-time wizard, Berth creates the admin from what you enter, as with bundled. |
| BTH 2 | 2 qBittorrent | Set the qBittorrent web UI login (skipped if that qBittorrent already has one). No global preference is written. | Enter its address and web UI login; a passing test completes the page. No global preference is written. |
| BTH 3 | 3 Library paths | Creates the libraries on the list (Movies / TV / Anime by default; you can rename, add and remove), then a Route for each library and runs every check on it. On a first visit with an unchanged list this starts as soon as the page opens, and shows which check each Route is on. | Tick the libraries and their write target. **Build and check** adds a Berth path to each ticked library (existing paths are left alone), creates the Routes and runs every check. |
| BTH 4 | 4 Prowlarr | The API key is read from Prowlarr's config through a read-only mount. One press tests the nine recommended public indexers and adds those that pass (each labelled with its language; any that tested fine but could not be added are listed separately). The web UI login reuses page 1's. Then try a search and remove what you don't want. Picking indexers one by one, and other public indexers, are under **Advanced**. | Paste the API key and use the indexers you already have. You can also test the recommended public indexers and add the ones you tick (yours are never removed). Then try a search. |
| BTH 5 | 5 TMDB | Paste your own API key and press **Test TMDB**. | Same. |
| — | 6 Finish | Says what you skipped and where to finish it. | Same. |

**A Route** is the path a download takes into one library: qBittorrent's download folder for that library, the
`complete` folder, and the library folder Jellyfin reads. Each Route is created with a real test: Berth writes a
probe file, hardlinks it, and compares inode numbers as seen from Berth, qBittorrent and Jellyfin. If the three
containers do not see the same filesystem, the check fails right there and says which container is missing which
mount. You can only move on when every check is green, so a wrong mount shows up on page 3 — before you go and
get a TMDB key.

Each page stops on its result; press **Next berth** to go on. Berths you have passed on the board can be clicked
to go back, and each page has **Previous berth**. The page is in the URL (`/setup?step=N`): the browser's back
button returns to the previous page you looked at, and reload stays where you are.

**The Prowlarr page can be skipped** with **Do this later** (you just won't find anything by searching). **The TMDB page
cannot**: without a key that passes the test there are no titles, seasons or posters, so the wizard stops on
page 5.

## Accounts and passwords

**Berth has no accounts of its own.** The account from page 1 is a Jellyfin admin and also the Berth *owner*;
you sign in to Berth with it from then on. Other people sign in with their own Jellyfin accounts, and Jellyfin
decides whether they are admins. Until there is an owner, the wizard only lets you choose Jellyfin and become the
owner; every later page needs you signed in. Whoever gets there first becomes the owner, as with Jellyfin's own
first-run wizard.

The **web UI logins** for the bundled qBittorrent and Prowlarr are set on their pages and are required. When
page 1 creates the bundled Jellyfin admin, **Use this login for the bundled qBittorrent and Prowlarr interfaces
too** is ticked: the password stays only in that browser tab's memory (not in Berth, not in the browser's
storage), is filled in on those two pages, and Berth checks it against Jellyfin before writing it. So you type
the password only twice, both on page 1. If you untick it, sign in to an existing admin on page 1, or reload in
between, those two pages ask again: the default reuses the Jellyfin login (the username is the owner, type the
password once); untick it to set a separate login (type the password twice).

Those logins are for you, to open those services' own interfaces. Berth itself does not need them (qBittorrent
lets Berth in through an address whitelist, Prowlarr through its API key).

What Berth stores: **never your Jellyfin password in plain text.** For the bundled qBittorrent and Prowlarr
logins it keeps the username and a salted scrypt hash of the password (when you reuse the Jellyfin login, that
is a hash of your Jellyfin password), only to tell whether a login is already set. The services' API keys are
stored as they are; see [Backup, secrets and reinstalling](backup-and-reinstall.md). If a service already has a
login (you reinstalled and kept its config), the wizard does not make you set it again. Change them later under
**Settings → qBittorrent / Prowlarr → Interface login**: a plain change-login form (username, new password
twice, **Save**). Reusing the Jellyfin login is only offered in the wizard.

## What Berth changes in your services

The same for both choices: **Berth only creates things it owns** — the "Berth" API key, a Berth path or the
libraries on its list, `berth-*` categories in qBittorrent, and the indexers you choose to add. It does not change
logins or global preferences, and leaves your existing libraries and indexers alone. The bundled services get one
more thing each, so you can sign in to them: the Jellyfin admin, and the qBittorrent and Prowlarr web UI logins.

Known exceptions, tracked as open issues: Berth asks Jellyfin to scan all libraries when an import does not show
up ([62](../../.scratch/m4/issues/62-jellyfin-scan-scope.md)), tags every torrent it sends with `berth`, and
recreates a `berth-*` category you deleted the next time it sends a torrent
([66](../../.scratch/m4/issues/66-takeover-list-and-runtime-gate.md)). The tracking notes are in Chinese.

## After the wizard

The wizard closes and the owner goes straight into Berth. The **Health** page reruns the same checks every
5 minutes. Opening `/setup` again takes you to **Settings → Jellyfin**, which says the wizard is done and that
changes are made here.

| Page | What it is for |
| --- | --- |
| Discover `/` | TMDB trending, popular and search. Each tile opens that title's page. |
| Title page `/media/:id` | Season and episode table; search the indexers for torrents (results show tags and the seasons and episodes they appear to contain); pick a Route and send (the folder name it will use is shown first); what is already imported, in which versions, and whether Jellyfin has found it. |
| Downloads `/jobs` | Every download you sent, with live status and progress. Expand a row for its timeline and import plan (per file: what Berth will do, how sure it is, the target path, and why). Failed sends, failed imports and items waiting for review each have their next step. |
| Library `/library/:library` | One page per Jellyfin library, showing only what you can see in Jellyfin: the whole library, 50 titles per page (not just what Berth imported; posters come from Jellyfin through Berth). Titles Berth handled show how many episodes were imported and whether one is waiting for you. Each tile shows where you are (watched, percentage, episodes left); mark watched or unwatched (written back to your Jellyfin account). Titles not yet in Jellyfin are listed separately. |
| Review `/review`, Issues `/issues` | Imports Berth was not sure about, and problems found by the nightly check (a deleted episode, a hardlink replaced by a copy, a torrent nobody claimed). Admins only. |
| RSS `/rss` | Mikan feeds, and Nyaa or acg.rip search feeds: new episodes are sent and imported on their own. |
| Health `/health` | The four health checks and the download loop. Every user can see it. |
| Settings `/settings/*` | Admins only. One page per berth: **Jellyfin** (health and recheck, an existing server's address and sign-in, the public URL), **qBittorrent** (health, an existing server's address and login, the bundled one's web UI login, the free-space threshold), **Library paths** (add Routes — a library can have a second one — rename, disable, recheck, delete), **Prowlarr** (add indexers, try a search, remove; an existing server's URL or key), **TMDB** (replace the key and test it). |

To start the wizard over, see [Backup, secrets and reinstalling](backup-and-reinstall.md#rerunning-the-wizard).
