---
name: missing-episodes
description: >-
  Download one season the library does not have yet, or fill in the aired episodes a series is
  missing: find out which are missing and why, search for releases under several names, and
  put the picks on one confirmation card. Use when the user asks to download a season, fill
  gaps, complete a season, or get the episodes they do not have yet.
tools:
  - discover.search_media
  - why_not.explain
  - inventory.find_in_library
  - search.search_torrents
  - media.read_media
  - downloading.add_manual_download
---

Diagnose before downloading: a download for an episode that is already on its way, waiting
in Review, or already in the user's Jellyfin makes a duplicate.

1. Find the work with `discover_search_media` unless an earlier tool result gave its media_id.
2. Read it with `media_read_media`. Episodes `in_jellyfin` are already in the user's Jellyfin
   (copied in by hand, or imported before Berth's records were lost): they are not missing, so
   do not search or download them unless the user asks for another version. In your reply
   before any card, say in one line which episodes Jellyfin already has (by season, with
   ranges). If `jellyfin` is `unknown`, Berth could not ask Jellyfin:
   say so before searching. When a whole season or more is `in_jellyfin`, say Berth does not
   know those files and suggest rebuilding the ledger: the button "從媒體庫重建帳本" ("Rebuild
   the ledger from the library") at the top of Berth's Issues page (待處理); a non-admin asks
   an admin. If the work is not found on TMDB, `inventory_find_in_library` tells whether the
   user has it under another name.
3. Call `why_not_explain` for the whole work (no episode). Only episodes concluded `no_source`
   or `download_failed` need a new download. For the rest, do not search:
   - `downloading`, `awaiting_review`, `jellyfin_pending`: already on the way; say so.
   - `excluded`, `unbound`: the RSS feed has them. The fix is in Berth's RSS page (release the
     item, or bind the RSS Series), not a second torrent. Tell the user.
   - `import_failed`: the file is here but importing failed; point to that job.
   `why_not_explain` reads Berth's records only: an episode it calls `no_source` that
   `media_read_media` shows as `in_jellyfin` is not missing.
4. Tell the user which episodes you will look for, by season with ranges, before searching.
5. Search one season at a time with `search_search_torrents`: media_id and
   `scope: {missing: true, season: <n>}`. That asks only for the episodes still missing, but
   when they are many it asks for the whole season, so rows for episodes already imported or
   `in_jellyfin` can still come back: leave those rows out. It asks the names Berth's search
   settings turn on; `attempts` shows which. The language of a search
   decides which subtitles come back (Chinese titles find mostly Chinese subtitles, English and
   original titles every language), so search under several names:
   - the original and the English title (`title_original`, `title_en` from `media_read_media`),
     with `query` for any not in `attempts`;
   - with `query`, the title in the language the user writes in: `title` for Traditional
     Chinese, and for Chinese also the Simplified title most subgroups write; for other
     languages your own knowledge or a web search, saying which (cite the URL, or say it is
     from memory);
   - when results are thin, other names with `query`: romaji, the name with the season
     (`<name> S02`, `<name> Season 2`, `<name> 第2季`), or the name one subgroup uses.
   A `query` search replaces `scope`, so its rows are judged only against the words you typed:
   check each row's season and episodes yourself, and leave out rows that only cover episodes
   the user already has.
6. Pick releases. Follow what the user said about subtitle language and subgroups first; when
   they said nothing, prefer subtitles in the language they write in. Then, in order:
   - `verdict: fits`;
   - one season pack covering several missing episodes over many single episodes;
   - more seeders, then smaller size for the same quality.
   A pack that also holds episodes already imported or in Jellyfin is fine; say so. If nothing fits, say which
   episodes have no release and stop there for them.
   Write a short table of the candidates in your reply, grouped by subtitle language
   (subgroup, episodes covered, resolution, seeders, size), and say which you would pick and
   why: the card shows only the picks, so the table is where the user sees what else there was.
   If the user has not said which subtitles or subgroup they want and the candidates come in
   more than one subtitle language, end that reply by asking and stop there: no
   `downloading_add_manual_download` call until they answer. Otherwise propose the card right
   after the table.
7. Pick the route from `media_read_media` for the work: its `routes` are the ones that hold
   this kind of work, and `default_route_id` is the one used last. Pass that one, or any of
   `routes` when there is none. Do not ask in chat: when more than one fits, the card makes the
   user choose the route for that row.
8. Put every pick in one `downloading_add_manual_download` proposal, one row per torrent:
   the release picked from the search results, media_id, route_id. Say which episodes each row
   covers and its subgroup and subtitle language. The user confirms the card; do not claim
   anything was sent before that.
9. After the card is decided, report per row what happened; some rows can fail while others
   succeed.
