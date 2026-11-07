---
name: subscribe
description: >-
  Subscribe a still-airing series so Berth keeps downloading new episodes: compare the
  subgroups releasing it, let the user pick, then propose the subscription.
tools: [discover.search_media, media.read_media, rss.list_subscriptions, rss.delete_feed,
        search.search_torrents, rss.subscribe]
---

1. Identify the work with `discover_search_media`, read it with `media_read_media`
   (`aired_blocks`), and `rss_list_subscriptions` for what it already has.
2. `search_search_torrents` under its names. One table, a row per subgroup: subtitle language,
   resolution, latest episode and its date, usual delay after airing (estimate from
   `published_at`; "—" when you cannot tell), seeders.
3. Recommend one and ask which, unless the user already picked. If the work already has a
   subscription, say so and ask whether to delete it (`rss_delete_feed`).
4. `rss_subscribe` with the work's media_id and the subgroup you recommend. The card lists the
   subgroups found; the user picks the subgroup and its source there.
5. A site that cannot be reached: say which; do not switch sources on your own.
