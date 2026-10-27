---
name: series-mapping
description: >-
  Map a whole anime franchise (every season, split cour, OVA and movie) to TMDB entries and
  episode ranges, then let the user choose what to download. Use when the user wants all of a
  series, "every season", a franchise, or asks how its seasons line up with TMDB.
tools:
  - anilist.search_anime
  - anilist.read_franchise
  - fribb.lookup_anime
  - discover.search_media
  - media.read_media
  - search.search_torrents
  - downloading.add_manual_download
---

1. Find the first season on AniList with `anilist_search_anime`. If the title finds nothing, try
   the romaji or the original Japanese title.
2. Walk the franchise with `anilist_read_franchise` (sequels, prequels, side stories, summaries;
   leave spin-offs out unless the user asks for them). Keep each entry's format and episode
   count.
3. Map every AniList entry to TMDB with `fribb_lookup_anime` (all ids in one call). A TV entry
   gives its `media_ids`, the TMDB season and `first_tmdb_episode`.
   - **`first_tmdb_episode` is offset + 1**; the entry's last episode is offset + its episode
     count. TMDB often folds several cours into one season (all of Re:Zero's seasons 2–4 sit in
     TMDB season 1).
   - **Check that the ranges in one TMDB season follow each other with no overlap and no gap.**
     Fribb's offsets are sometimes off by one: for Re:Zero, season 1 has 25 episodes and the next
     cour's offset is 26, which would start it at E27 and overlap the cour after it (offset 38,
     starting at E39). When ranges overlap or leave a gap, chain them from the episode counts
     instead, and check the end against the TMDB season's episode count from `media_read_media`.
     Say on the table which ranges you corrected and why.
4. Movies, and many OVAs, are separate TMDB movies, or land in TMDB's specials (season 0).
   For entries in `unmapped`, and for a movie or OVA that Fribb maps only to specials (season
   0), search its title with `discover_search_media`: a theatrical release is usually its own
   TMDB movie. Mark that row "matched by title, please check" on the table.
   The confirmation card has no place for notes, so the table is where the user sees it.
5. Read every TMDB entry with `media_read_media`: confirm it exists and see how many episodes
   are already imported. Do not offer what is already there.
6. Show the user one table before searching anything:
   AniList entry | format | episodes | TMDB entry and SxxEyy range | already imported.
   Leave shorts, recaps and spin-offs unticked and ask which rows they want.
7. Only after they choose, search with `search_search_torrents`, one TMDB entry (or one
   season) at a time. Anime releases often need a `query` with the romaji or the fansub
   group's name for the show. Prefer `verdict: fits`, more seeders, and whole-season packs.
8. Pick each row's route from that TMDB entry's `media_read_media`: its `routes` hold that kind
   of work (series or movies) and `default_route_id` is the one used last. A movie and a series
   never share a route. If more than one fits and there is no default, ask.
9. Put all picks in one `downloading_add_manual_download` proposal, one row per TMDB entry or
   season, each row saying which AniList entries it covers. The user confirms the card.
