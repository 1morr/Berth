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
2. Read the TMDB series with `media_read_media`: its seasons, each season's episode count,
   which episodes sit in specials (season 0), and `aired_blocks` (runs of episodes that aired
   without a long break, with their first and last air dates).
3. List the franchise's parts in airing order: every TV season and split cour, OVAs and movies,
   with each part's episode count and first air date.
   - **With web search** (`web_search`, or the Tavily search tool): search once or twice for a
     page that lists the seasons and their episodes (for example "<title> list of episodes" on
     Wikipedia or an anime database), and cite the URL. Leave spin-offs, recaps and shorts out
     unless the user asks for them.
   - **Without web search, or when the search finds no such page**: do not fill the list from
     memory. Cut the TMDB seasons into parts at the breaks in `aired_blocks` (each block is
     usually one cour), name each part by when it aired, and mark **every** TMDB season
     "沒有網頁核對，請確認" (not checked against a web page, please check), in the user's language.
     If you add anything you remember (a part's name, an episode count), say it is from memory.
4. Map each TV part to a TMDB season and range by **chaining**: the first part starts at S01E01,
   each next part right after the last, and once a TMDB season's episode count is used up the
   next part starts at E01 of the next season. TMDB often folds several cours or even seasons
   into one TMDB season (all of Re:Zero's seasons 2–4 sit in TMDB season 1).
   **Mark the whole TMDB season "未經核對，請確認"** (the same words in the user's language) when
   any of these is true, and show your range and the reason instead of guessing a fix:
   - the parts' episode counts do not add up to that season's episode count, or chaining runs
     past it;
   - the season continues the numbering of the one before it (its first episode is not E01,
     like Hunter x Hunter (2011), whose season 2 starts at E63), or a part runs from one TMDB
     season into the next: then mark both seasons;
   - **any part in it has an episode 0, a .5 episode, or a recap, or TMDB moved one of that
     part's episodes to specials.** This one has no exceptions, even when the counts add up:
     an episode moved to specials shifts every range after it (Mushoku Tensei season 2 is
     E01–E12 on TMDB because its episode 0 is S00E02, though lists say 13 episodes).
   Every row in a marked season carries the mark, not just the row that looks off.
5. Movies, and many OVAs, are separate TMDB movies or land in TMDB's specials (season 0).
   Search each one's title with `discover_search_media`: a theatrical release is usually its
   own TMDB movie. Mark that row "matched by title, please check".
6. Read every TMDB entry with `media_read_media`: confirm it exists and see how many episodes
   are already imported. Do not offer what is already there.
7. Show the user one table before searching for any release:
   part | format | episodes | TMDB entry and SxxEyy range | already imported | mark.
   The confirmation card has no place for notes, so the table is where the user sees the marks.
   Leave shorts, recaps and spin-offs unticked and ask which rows they want.
8. Only after they choose, search with `search_search_torrents`. A franchise has many parts,
   and every search stays in this turn's context, so keep the searches few. The language of a
   search decides which subtitles come back (Chinese titles find mostly Chinese subtitles,
   English and original titles every language):
   - First, one search without `query` for each TMDB entry: it asks the names Berth's search
     settings turn on (`attempts` shows which) for every season at once.
   - Then, only for parts with no fitting release yet, **one** `query` per part with one name:
     the title in the language the user writes in, with the part's season (`<name> 第2季`,
     `<name> S02`). For Chinese use the Simplified title most subgroups write; for other
     languages your own knowledge or a web search, saying which.
   - Only for a part still without one, one more `query` with another name (the original,
     English or romaji title, or the name one subgroup uses). Then stop for that part and say
     it has no release; do not try more spellings or keywords like "batch" or "合集".
   A `query` search is judged only against the words you typed: check the season and episodes
   of each row yourself. Follow what the user said about subtitle language and subgroups;
   when they said nothing, prefer subtitles in the language they write in. Then prefer
   `verdict: fits`, more seeders, and whole-season packs.
9. Pick each row's route from that TMDB entry's `media_read_media`: its `routes` hold that kind
   of work (series or movies) and `default_route_id` is the one used last. A movie and a series
   never share a route. Pass the default, or any of `routes` when there is none. Do not ask in
   chat: when more than one fits, the card makes the user choose the route for that row.
10. Put all picks in one `downloading_add_manual_download` proposal, one row per TMDB entry or
    season, each row saying which parts it covers and its subgroup and subtitle language. The
    user confirms the card.
