---
name: recommend
description: >-
  Recommend this season's new anime, or trending series and movies, then subscribe or
  download what the user picks. Use when asked what is new or good, or what to watch.
tools: [anilist.read_season, bgm.read_calendar, discover.read_trending,
        inventory.find_in_library, rss.list_subscriptions]
---

1. Candidates: `anilist_read_season` for anime, adding Chinese titles and Bangumi scores from
   `bgm_read_calendar`; `discover_read_trending` for everything else.
2. One `inventory_find_in_library` call with every name and one `rss_list_subscriptions` call:
   mark "have" (`exact` matches only) and "subscribed", and do not recommend those again.
3. Per candidate: titles, format and episodes, scores with their rater counts (under 20 is
   "too few ratings", not ranked), one line of genre; say when sources disagree.
4. Reviews only when asked: at most two web searches, cite URLs.
5. When the user picks: still airing → load `subscribe`; finished → load `download`.
