---
name: series-mapping
description: >-
  Map a whole anime franchise (every season, split cour, OVA and movie) to TMDB entries and
  episode ranges, then let the user choose what to download. Use when the user wants all of a
  series, "every season", a franchise, or asks how its seasons line up with TMDB.
tools:
  - discover.search_media
  - media.read_media
  - search.search_torrents
  - downloading.add_manual_download
---

1. Find the series on TMDB with `discover_search_media`. Try the English, romaji and original
   Japanese titles; keep only results with `animation: true`. When more than one is left (a
   remake shares its title with the original), pick the one whose `year` matches the version
   the user asked for, and say which one you picked.
2. List the franchise's parts in airing order: every TV season and split cour, OVAs and movies,
   with each part's episode count and first air date. If web search is available, search once
   or twice on an anime database or Wikipedia page that lists the seasons (for example
   "<title> list of episodes" or "<title> anime seasons"), and cite the URL. Leave spin-offs,
   recaps and shorts out unless the user asks for them. Without web search, use what you know
   and say the list is from memory.
3. Read the TMDB series with `media_read_media`: its seasons, each season's episode count and
   episode numbers. Then map each TV part to a TMDB season and range by **chaining**: the first
   part starts at S01E01, each next part right after the last, and once a TMDB season's episode
   count is used up the next part starts at E01 of the next season.
   - TMDB often folds several cours or even seasons into one TMDB season (all of Re:Zero's
     seasons 2–4 sit in TMDB season 1), and sometimes keeps an episode in specials (an episode
     0, a recap), which shifts everything after it.
   - **Mark the whole TMDB season "未經核對，請確認"** (the same words in the user's language)
     when the parts' episode counts do not add up to that season's count, when chaining runs
     past it, when the season continues the numbering of the one before it (its first episode
     is not E01), or when a part has an episode 0 or a recap. Show your range and why, and do
     not guess a fix.
4. Movies, and many OVAs, are separate TMDB movies or land in TMDB's specials (season 0).
   Search each one's title with `discover_search_media`: a theatrical release is usually its
   own TMDB movie. Mark that row "matched by title, please check".
5. Read every TMDB entry with `media_read_media`: confirm it exists and see how many episodes
   are already imported. Do not offer what is already there.
6. Show the user one table before searching anything:
   part | format | episodes | TMDB entry and SxxEyy range | already imported.
   Leave shorts, recaps and spin-offs unticked and ask which rows they want.
7. Only after they choose, search with `search_search_torrents`, one TMDB entry (or one
   season) at a time. Anime releases often need a `query` with the romaji or the fansub
   group's name for the show. Prefer `verdict: fits`, more seeders, and whole-season packs.
8. Pick each row's route from that TMDB entry's `media_read_media`: its `routes` hold that kind
   of work (series or movies) and `default_route_id` is the one used last. A movie and a series
   never share a route. If more than one fits and there is no default, ask.
9. Put all picks in one `downloading_add_manual_download` proposal, one row per TMDB entry or
   season, each row saying which parts it covers. The user confirms the card.
