---
name: why-not-imported
description: >-
  Diagnose why a series, a movie or one episode is not in the library yet, or what is stuck.
  Use whenever the user asks why something is missing, not imported, not showing in Jellyfin
  or stuck, even before calling any other tool.
tools:
  - discover.search_media
  - why_not.explain
---

Read only. Do not propose downloads or changes while diagnosing; say what to do at the end.

1. Find the work. If no earlier tool result gave its media_id, call `discover_search_media` with
   the title. If several results could be it, ask the user which one (show year and kind).
2. Call `why_not_explain` with the media_id. If the user named one episode, pass
   `episode: [season, episode]` using TMDB numbering; if they used fansub or "cour" numbering,
   say how you mapped it.
3. Read the conclusion for each episode. They mean:
   - `import_failed`: downloaded, but importing it failed. Someone has to look at that job.
   - `download_failed`: never downloaded: the submit failed, the client reported an error,
     files went missing, the torrent was removed from qBittorrent, or an RSS submit was refused.
   - `awaiting_review`: downloaded and waiting in Review for an admin.
   - `unbound`: an RSS feed has the episode, but its RSS Series is not bound to a work yet.
   - `excluded`: an RSS feed has the episode, but an exclusion rule or "only new episodes"
     skipped it.
   - `no_source`: aired, but there is no job and no RSS item for it anywhere.
   - `downloading`: on its way; it will finish by itself unless the job is stalled.
   - `jellyfin_pending`: imported, but Jellyfin has not picked the file up yet.
   - `unaired`: not aired yet, or TMDB has no air date.
   - `imported`: it is there.
4. The result carries, for each conclusion, the jobs behind it with their latest events, the
   open issues and the RSS items. Use them as the evidence; a job stuck in one state for a long
   time is worth pointing out even when its conclusion is `downloading`.
   For a user who is not an admin, `issues` and `rss` are null and `jobs` holds only the
   downloads they sent themselves, while the conclusions still count everyone's. A conclusion
   with no job or item behind it means someone else's download or an RSS feed covers it: say
   so, without guessing details.
5. Answer with the conclusion first, grouped by reason and with episode ranges ("S01E05–E08:
   no source"), then the evidence: job state, issue, RSS item. Say only what the records show;
   if the cause behind a state is not in them, say you cannot tell from Berth's records.
6. End with the next step: the Berth page and button (Review, the job's Retry, binding the RSS
   Series, releasing the RSS item) or, for `no_source`, offer to search for a release. Review
   and the RSS page are for admins: a user who is not one should ask an admin, and can retry
   only the downloads they sent.
