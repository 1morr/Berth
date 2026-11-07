---
name: subscribe
description: >-
  Subscribe a still-airing series so Berth keeps downloading new episodes: compare the
  subgroups releasing it, let the user pick, then propose the subscription.
tools: [discover.search_media, media.read_media, rss.list_subscriptions, rss.delete_feed,
        bangumi.search_bangumi, bangumi.read_bangumi, search.search_torrents,
        rss.subscribe_mikan, rss.subscribe_search]
---

1. Find the work with `discover_search_media` and read it with `media_read_media`: its names,
   and which episodes have aired and when (`aired_blocks`).
2. `rss_list_subscriptions` for the work: what it already has (site, subgroup).
3. Find the subgroups. Mikan: `bangumi_search_bangumi` with the Chinese title first, then the
   original, romaji and English titles until one finds the bangumi; `bangumi_read_bangumi`
   for its subgroups. Several hits: pick the one whose air date matches the work, and say so.
   Releases: `search_search_torrents` with the work's media_id and no `query` (`attempts`
   shows which names Berth asked), then a `query` search under its other names.
4. Show one comparison table, one row per subgroup: subgroup | subtitle language |
   resolution | latest episode and its date | usual delay after airing | seeders | on Mikan.
   Delay is the release's `published_at` minus that episode's air date (count weekly from the
   `aired_blocks` start): an estimate, never an invented number. Subtitle language comes from
   the release name or `tags` (CHT / 繁 = Traditional Chinese, CHS / 简 = Simplified, ENG,
   multi-sub). Recommend one: what the user asked for; then keeping up (latest episode, short
   delay); then resolution and seeders.
5. Ask which subgroup and stop there: no subscription call in that reply. If the work already
   has a subscription, say which and ask whether to delete it (`rss_delete_feed`, its own
   card). Skip the wait only when the user already picked one.
6. Propose the subscription:
   - On Mikan: `rss_subscribe_mikan` with the bangumi_id and subgroup_id.
   - Only when Mikan does not have it: `rss_subscribe_search` with kind `nyaa` or `acgrip`, a
     `term` as that subgroup names the show, and its `subgroup`. The card lists the first batch.
7. A site that cannot be reached (Mikan, nyaa, acg.rip or the indexers): say which and suggest
   trying again later. Do not switch sources on your own: offer it, and wait for the user.
