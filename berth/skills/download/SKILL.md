---
name: download
description: >-
  Download a movie, a season, the episodes a series is missing, or every part of a
  franchise. Use when asked to download, complete or fill in something, or wants all seasons.
tools: [discover.search_media, media.read_media, why_not.explain,
        inventory.find_in_library, search.search_torrents, downloading.add_manual_download]
---

1. Identify the work with `discover_search_media`; when several could be it, ask (year, kind).
   `inventory_find_in_library` says whether the user has it under another name, with the
   episodes the library holds (Jellyfin's numbering).
2. `media_read_media` for what the user has; `why_not_explain` for the whole work: only
   `no_source` and `download_failed` need a download, the rest say what is happening. When
   `jellyfin` is unknown, say Berth could not check it.
3. Franchise or "all seasons" only: list the parts in airing order with their TMDB entry and
   SxxEyy range. Check against a web page when web search is available and cite it; otherwise
   cut seasons at the breaks in `aired_blocks`. Mark `unchecked` every season you could not
   check, whose counts do not add up, whose numbering continues from the season before or runs
   into the next, or that holds an episode 0, a .5, a recap, or a part TMDB moved to
   specials: each shifts every later range. Show the table and ask which parts.
4. Say which episodes you will look for, then search with `search_search_torrents`: once per
   season with `scope: {missing: true, season: n}`, then `query` for names not in `attempts`.
   Use `contains` to list one subgroup's releases instead of episode by episode.
5. Reply with a candidates table grouped by subtitle language (subgroup, episodes,
   resolution, seeders, size) and your pick: what the user asked for; then `verdict: fits`;
   a season pack over single episodes; more seeders; smaller size. If the user has not said
   which subtitles and there is more than one language, ask and stop.
6. One `downloading_add_manual_download` card, a row per torrent with the episodes it covers.
