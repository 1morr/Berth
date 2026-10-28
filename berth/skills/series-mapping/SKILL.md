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
3. Work out each TV entry's TMDB season and episode range **two ways**, and read the TMDB
   series with `media_read_media` (its seasons, episode counts and episode numbers).
   - **A, the mapping table**: `fribb_lookup_anime` (all ids in one call) gives each entry's
     `media_ids`, TMDB season and `first_tmdb_episode` (offset + 1); its last episode is
     `first_tmdb_episode` + its AniList episode count − 1.
   - **B, chaining**: take the TV entries in airing order; the first starts at S01E01, each
     next one right after the last, and once a TMDB season's episode count is used up the next
     entry starts at E01 of the next season.
   - TMDB often folds several cours into one season (all of Re:Zero's seasons 2–4 sit in TMDB
     season 1), and both ways can be wrong: the table's offsets are sometimes stale or off by
     one, and chaining is off when TMDB keeps an episode in specials (an episode 0, a recap).
   - **Mark the whole TMDB season "兩種算法不一致，請確認"** (the same words in the user's
     language) when any entry in it gets a different range from A and B, when B runs past that
     season's episode count, or when the season continues the numbering of the one before it
     (its first episode is not E01, like Hunter x Hunter (2011), whose season 2 starts at E63).
     Show both ranges for those rows and do not pick one yourself.
   - **If `fribb_lookup_anime` fails** (the mapping table cannot be downloaded right now), use B
     alone. Find the series with `discover_search_media`: try the AniList entry's English,
     romaji and native titles in that order, keep only results with `animation: true`, and when
     more than one is left pick the one whose `year` is closest to the year the first AniList
     season started (remakes share their title with the original). If the counts do not add up
     to the TMDB seasons, say so instead of guessing. Mark every row mapped this way
     "未經對照表，請確認" (not checked against the mapping table, please check), in the user's
     language.
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
   never share a route. Pass the default, or any of `routes` when there is none. Do not ask in
   chat: when more than one fits, the card makes the user choose the route for that row.
9. Put all picks in one `downloading_add_manual_download` proposal, one row per TMDB entry or
   season, each row saying which AniList entries it covers. The user confirms the card.
