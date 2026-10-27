---
name: missing-episodes
description: >-
  Fill in the aired episodes a series is missing: find out which are missing and why, search
  for releases and put the picks on one confirmation card. Use when the user asks to fill gaps,
  complete a season, or get the episodes they do not have yet.
tools:
  - discover.search_media
  - why_not.explain
  - search.search_torrents
  - media.read_media
  - downloading.add_manual_download
---

Diagnose before downloading: a download for an episode that is already on its way, or waiting
in Review, makes a duplicate.

1. Find the work with `discover_search_media` unless an earlier tool result gave its media_id.
2. Call `why_not_explain` for the whole work (no episode). Only episodes concluded `no_source`
   or `download_failed` need a new download. For the rest, do not search:
   - `downloading`, `awaiting_review`, `jellyfin_pending`: already on the way; say so.
   - `excluded`, `unbound`: the RSS feed has them. The fix is in Berth's RSS page (release the
     item, or bind the RSS Series), not a second torrent. Tell the user.
   - `import_failed`: the file is here but importing failed; point to that job.
3. Tell the user which episodes you will look for, by season with ranges, before searching.
4. Search one season at a time with `search_search_torrents`: media_id and
   `scope: {missing: true, season: <n>}`. Prefer, in order:
   - `verdict: fits`;
   - one season pack covering several missing episodes over many single episodes;
   - more seeders, then smaller size for the same quality.
   A pack that also holds episodes already imported is fine; say so. If nothing fits, say which
   episodes have no release and stop there for them.
5. Pick the route from `media_read_media` for the work: its `routes` are the ones that hold
   this kind of work, and `default_route_id` is the one used last. Use that one; if there is
   none and more than one route fits, ask.
6. Put every pick in one `downloading_add_manual_download` proposal, one row per torrent:
   the release picked from the search results, media_id, route_id. Say which episodes each row
   covers. The user confirms the card; do not claim anything was sent before that.
7. After the card is decided, report per row what happened; some rows can fail while others
   succeed.
