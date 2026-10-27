"""「為什麼沒入庫」的聚合讀取命令（M5 票 10，plan §11.6〈分段〉第 4 段）。

一部作品（或其中一集）的答案散在五張表：季表、Job 與事件、Issue、RSS 那一側、帳本。這裡每一種
結論各一個情境，資料列直接擺進去（安排照 `test_inventory.py`），斷言只看 `explain` 回的那一份。
誰看得到什麼（一般使用者只看得到自己的 Job）在 `test_why_not_api.py`。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EpisodeStatus,
    EventType,
    FeedItemStatus,
    FeedKind,
    IssueStatus,
    IssueType,
    JobState,
    PlanAction,
    PlanStatus,
    Role,
    WhyNot,
    WhyNotRefusal,
)
from berth.models import Event, Issue, Media, RssFeed, RssItem, RssSeries
from berth.models.types import utcnow
from berth.services.why_not import WhyNotRejectedError, WhyNotView, explain
from tests.integration.test_inventory import film, job, linked, plan, route, season, title

pytestmark = pytest.mark.asyncio

ADMIN = 1
SPY_02 = "[LoliHouse] SPY x FAMILY - 02 [WebRip 1080p HEVC-10bit AAC]"


async def why(
    session: AsyncSession,
    media_id: str,
    episode: tuple[int, int] | None = None,
    *,
    role: Role = Role.ADMIN,
    user_id: int = ADMIN,
) -> WhyNotView:
    return await explain(session, media_id, episode=episode, role=role, user_id=user_id)


async def spy(session: AsyncSession) -> Media:
    """第一季播了三集、還有一集沒播。"""
    return await title(session, seasons=(season(1, aired=3, unaired=1),))


async def series(
    session: AsyncSession, media: Media, *, bound: bool = True, exclude: tuple[str, ...] = ()
) -> RssSeries:
    """一個 Mikan 的 RSS Series：綁到 `media`，或待綁定而候選裡有它。"""
    row = RssSeries(
        key=f"mikan:3600:{int(bound)}",
        title_raw=SPY_02,
        media_id=media.id if bound else None,
        candidates_json=None if bound else [media.id],
        exclude_json=list(exclude),
    )
    session.add(row)
    await session.commit()
    return row


async def mikan(session: AsyncSession) -> RssFeed:
    """Feed Item 都掛在同一個 Mikan 聚合 feed 上。"""
    found = await session.scalar(select(RssFeed))
    if found is None:
        found = RssFeed(name="Mikan", url="https://mikanani.me/RSS/MyBangumi", kind=FeedKind.MIKAN)
        session.add(found)
        await session.commit()
    return found


async def item(
    session: AsyncSession,
    owner: RssSeries,
    status: FeedItemStatus,
    *,
    title: str = SPY_02,
    error: str = "",
    skip: dict[str, object] | None = None,
) -> RssItem:
    row = RssItem(
        feed_id=(await mikan(session)).id,
        guid=f"{title}-{status}",
        title=title,
        series_id=owner.id,
        status=status,
        error=error,
        skip_json=skip,
    )
    session.add(row)
    await session.commit()
    return row


class TestConclusions:
    """每一種結論一個情境（票 10 驗收第一條）。"""

    async def test_an_aired_episode_nobody_went_for_has_no_source(
        self, session: AsyncSession
    ) -> None:
        media = await spy(session)

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.NO_SOURCE
        (verdict,) = found.episodes
        assert (verdict.season, verdict.episode, verdict.status) == (1, 2, EpisodeStatus.MISSING)

    async def test_an_episode_still_to_air_is_unaired(self, session: AsyncSession) -> None:
        media = await spy(session)

        assert (await why(session, media.id, (1, 4))).conclusion is WhyNot.UNAIRED

    async def test_an_episode_jellyfin_found_is_imported(self, session: AsyncSession) -> None:
        tv = await route(session)
        media = await spy(session)
        await linked(session, media, tv, episode=2, item="jf-2")

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.IMPORTED

    async def test_a_linked_episode_jellyfin_has_not_found_yet_is_pending(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        media = await spy(session)
        await linked(session, media, tv, episode=2, resolve_after=utcnow() + timedelta(minutes=5))

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.JELLYFIN_PENDING

    async def test_an_episode_a_job_is_bringing_is_downloading(self, session: AsyncSession) -> None:
        tv = await route(session)
        media = await spy(session)
        coming = await job(session, media, tv, JobState.DOWNLOADING)
        await plan(session, coming, (PlanAction.IMPORT, 1, 2), status=PlanStatus.PREPLAN)

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.DOWNLOADING
        assert found.episodes[0].jobs == (coming.hash,)
        assert [row.hash for row in found.jobs] == [coming.hash]

    async def test_a_job_without_a_file_list_claims_the_episode_its_name_says(
        self, session: AsyncSession
    ) -> None:
        """剛送單、還沒有檔案清單：季表說「缺」，這裡照發佈名猜得出是第 2 集。

        說「沒有來源」是錯的：那一集正在路上。"""
        tv = await route(session)
        media = await spy(session)
        sent = await job(session, media, tv, JobState.SUBMITTED)
        sent.name = SPY_02
        await session.commit()

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.DOWNLOADING
        assert (await why(session, media.id, (1, 3))).conclusion is WhyNot.NO_SOURCE

    async def test_an_episode_held_for_review_is_awaiting_review(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        media = await spy(session)
        held = await job(session, media, tv, JobState.REVIEW)
        await plan(session, held, (PlanAction.REVIEW, 1, 2), status=PlanStatus.PENDING_REVIEW)

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.AWAITING_REVIEW

    async def test_an_episode_whose_import_failed_says_so_with_its_open_issue(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        media = await spy(session)
        failed = await job(session, media, tv, JobState.IMPORT_FAILED)
        await plan(session, failed, (PlanAction.IMPORT, 1, 2), status=PlanStatus.FAILED)
        session.add_all(
            [
                Issue(type=IssueType.JOB_WITHOUT_FILES, subject=failed.hash, job_hash=failed.hash),
                Issue(
                    type=IssueType.CLIENT_ERROR,
                    subject=failed.hash,
                    job_hash=failed.hash,
                    status=IssueStatus.RESOLVED,
                ),
            ]
        )
        await session.commit()

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.IMPORT_FAILED
        assert [row.type for row in found.issues or ()] == [IssueType.JOB_WITHOUT_FILES]

    async def test_a_season_pack_qbittorrent_dropped_is_a_failed_download(
        self, session: AsyncSession
    ) -> None:
        """prototype 的 S4：整季合集送出 2 秒後被移出 qBittorrent（`client_removed`）。發佈名只寫了
        季，所以它蓋到那一季播出了的每一集：還沒播的第 4 集不在合集裡，第二季也不在。
        答案帶著它最後幾筆事件。"""
        tv = await route(session)
        media = await title(session, seasons=(season(1, aired=3, unaired=1), season(2, aired=1)))
        dropped = await job(session, media, tv, JobState.CLIENT_REMOVED)
        dropped.name = "[Flugel] SPY x FAMILY S01 (BD 1080p x264 Opus)"
        session.add_all(
            Event(job_hash=dropped.hash, type=kind.value, actor="1", payload_json={})
            for kind in (
                EventType.CREATED,
                EventType.SUBMITTED,
                EventType.ISSUE_DETECTED,
            )
        )
        await session.commit()

        found = await why(session, media.id)

        assert found.conclusion is WhyNot.DOWNLOAD_FAILED
        assert [(row.season, row.episode, row.conclusion) for row in found.episodes] == [
            (1, 1, WhyNot.DOWNLOAD_FAILED),
            (1, 2, WhyNot.DOWNLOAD_FAILED),
            (1, 3, WhyNot.DOWNLOAD_FAILED),
            (2, 1, WhyNot.NO_SOURCE),
        ]
        (shown,) = found.jobs
        assert shown.state is JobState.CLIENT_REMOVED
        assert [event.type for event in shown.events][-1] == EventType.ISSUE_DETECTED.value

    async def test_an_rss_item_the_exclusion_rules_held_back_is_excluded(
        self, session: AsyncSession
    ) -> None:
        media = await spy(session)
        owner = await series(session, media, exclude=("HEVC",))
        held = await item(
            session,
            owner,
            FeedItemStatus.EXCLUDED,
            skip={"code": "excluded", "params": {"rule": "HEVC", "layer": "series"}},
        )

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.EXCLUDED
        assert found.rss is not None
        assert [(row.id, row.bound, row.exclude) for row in found.rss.series] == [
            (owner.id, True, ("HEVC",))
        ]
        assert [(row.id, row.episode_start, row.skip) for row in found.rss.items] == [
            (held.id, 2, held.skip_json)
        ]

    async def test_an_rss_item_of_a_series_waiting_to_be_bound_is_unbound(
        self, session: AsyncSession
    ) -> None:
        media = await spy(session)
        waiting = await series(session, media, bound=False)
        await item(session, waiting, FeedItemStatus.UNBOUND)

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.UNBOUND
        assert found.rss is not None
        assert [(row.id, row.bound) for row in found.rss.series] == [(waiting.id, False)]

    async def test_an_rss_item_whose_send_keeps_being_refused_is_a_failed_download(
        self, session: AsyncSession
    ) -> None:
        """綁好了、還沒送成：沒被拒是下一輪就送（在路上），被拒了是沒下載成。"""
        media = await spy(session)
        owner = await series(session, media)
        await item(session, owner, FeedItemStatus.MATCHED, error="low_disk_space: 3 GB free")

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.DOWNLOAD_FAILED

    async def test_a_rejected_send_does_not_hide_another_one_still_queued(
        self, session: AsyncSession
    ) -> None:
        """同一集兩個字幕組：一筆被拒、一筆下一輪就送——那一集還是會來（code-review）。"""
        media = await spy(session)
        owner = await series(session, media)
        await item(session, owner, FeedItemStatus.MATCHED, error="low_disk_space: 3 GB free")
        await item(
            session, owner, FeedItemStatus.MATCHED, title="[ANi] SPY x FAMILY - 02 [1080P][WEB-DL]"
        )

        assert (await why(session, media.id, (1, 2))).conclusion is WhyNot.DOWNLOADING

    async def test_a_feed_failing_to_poll_is_one_of_the_open_issues(
        self, session: AsyncSession
    ) -> None:
        media = await spy(session)
        owner = await series(session, media, exclude=("HEVC",))
        held = await item(session, owner, FeedItemStatus.EXCLUDED)
        session.add(Issue(type=IssueType.FEED_POLL_FAILING, subject=str(held.feed_id)))
        await session.commit()

        found = await why(session, media.id, (1, 2))

        assert [row.type for row in found.issues or ()] == [IssueType.FEED_POLL_FAILING]


class TestWhoCoversWhat:
    """哪一筆蓋到哪一集。蓋不到任何認得的集時不能從回答裡消失（code-review）。"""

    async def test_a_pack_for_a_season_tmdb_does_not_have_covers_the_whole_title(
        self, session: AsyncSession
    ) -> None:
        """Re:Zero 的第二季在 TMDB 併進了第一季：發佈名寫 S2，TMDB 沒有第二季。說不出它不是哪一集，
        就算它蓋到整部作品播出了的每一集——第 0 季除外。"""
        tv = await route(session)
        media = await title(session, seasons=(season(0, aired=1), season(1, aired=2)))
        dropped = await job(session, media, tv, JobState.CLIENT_REMOVED)
        dropped.name = "[Judas] SPY x FAMILY S2 Part 1 [1080p][HEVC x265 10bit]"
        await session.commit()

        found = await why(session, media.id)

        assert [(row.season, row.episode, row.conclusion) for row in found.episodes] == [
            (1, 1, WhyNot.DOWNLOAD_FAILED),
            (1, 2, WhyNot.DOWNLOAD_FAILED),
        ]
        assert [row.hash for row in found.jobs] == [dropped.hash]

    async def test_a_plan_for_an_episode_tmdb_does_not_have_covers_the_whole_title(
        self, session: AsyncSession
    ) -> None:
        """計劃說 S02E05，TMDB 只有第一季：那一筆不能因為對不上季表就從回答裡消失。"""
        tv = await route(session)
        media = await title(session, seasons=(season(1, aired=2),))
        coming = await job(session, media, tv, JobState.DOWNLOADING)
        await plan(session, coming, (PlanAction.IMPORT, 2, 5), status=PlanStatus.PREPLAN)

        found = await why(session, media.id)

        assert [(row.episode, row.conclusion) for row in found.episodes] == [
            (1, WhyNot.DOWNLOADING),
            (2, WhyNot.DOWNLOADING),
        ]
        assert [row.hash for row in found.jobs] == [coming.hash]

    async def test_a_deleted_job_is_listed_but_does_not_count(self, session: AsyncSession) -> None:
        """「有人送過、後來刪了」也是答案；結論照樣是沒有來源。"""
        tv = await route(session)
        media = await spy(session)
        gone = await job(session, media, tv, JobState.REMOVED)
        gone.name = SPY_02
        await session.commit()

        found = await why(session, media.id, (1, 2))

        assert found.conclusion is WhyNot.NO_SOURCE
        assert [(row.hash, row.state) for row in found.jobs] == [(gone.hash, JobState.REMOVED)]


class TestWholeTitle:
    async def test_lists_only_the_episodes_with_something_to_say(
        self, session: AsyncSession
    ) -> None:
        """已入庫與還沒播的由季表的數字說；整部的結論是最需要人的那一種。"""
        tv = await route(session)
        media = await title(session, seasons=(season(0, aired=2), season(1, aired=3, unaired=1)))
        await linked(session, media, tv, episode=1, item="jf-1")
        held = await job(session, media, tv, JobState.REVIEW)
        await plan(session, held, (PlanAction.REVIEW, 1, 3), status=PlanStatus.PENDING_REVIEW)

        found = await why(session, media.id)

        assert (found.season, found.episode) == (None, None)
        assert [(row.season, row.episode, row.conclusion) for row in found.episodes] == [
            (1, 2, WhyNot.NO_SOURCE),
            (1, 3, WhyNot.AWAITING_REVIEW),
        ]
        assert found.conclusion is WhyNot.AWAITING_REVIEW
        assert [(row.season_number, row.aired, row.imported) for row in found.seasons] == [
            (0, 2, 0),
            (1, 3, 1),
        ]

    async def test_a_title_with_everything_aired_in_is_imported(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        media = await title(session, seasons=(season(1, aired=1, unaired=1),))
        await linked(session, media, tv, episode=1, item="jf-1")

        found = await why(session, media.id)

        assert (found.conclusion, found.episodes) == (WhyNot.IMPORTED, ())

    async def test_a_film_is_one_verdict(self, session: AsyncSession) -> None:
        movies = await route(session, "movies")
        oppenheimer = await film(session)
        coming = await job(session, oppenheimer, movies, JobState.STALLED)

        found = await why(session, oppenheimer.id)

        assert [(row.season, row.episode, row.conclusion) for row in found.episodes] == [
            (None, None, WhyNot.DOWNLOADING)
        ]
        assert found.episodes[0].jobs == (coming.hash,)

    async def test_a_film_in_jellyfin_is_imported(self, session: AsyncSession) -> None:
        """電影只有一格，問整部時也列它（code-review：曾經因為沒有季而說成還沒播）。"""
        movies = await route(session, "movies")
        oppenheimer = await film(session)
        await linked(
            session, oppenheimer, movies, season_number=None, episode=None, item="jf-movie"
        )

        found = await why(session, oppenheimer.id)

        assert found.conclusion is WhyNot.IMPORTED
        assert [row.conclusion for row in found.episodes] == [WhyNot.IMPORTED]


class TestRefusals:
    async def test_a_title_berth_has_never_seen(self, session: AsyncSession) -> None:
        with pytest.raises(WhyNotRejectedError) as raised:
            await why(session, "tv:999")

        assert raised.value.reason is WhyNotRefusal.MEDIA_MISSING

    async def test_a_film_has_no_episodes(self, session: AsyncSession) -> None:
        oppenheimer = await film(session)

        with pytest.raises(WhyNotRejectedError) as raised:
            await why(session, oppenheimer.id, (1, 1))

        assert raised.value.reason is WhyNotRefusal.NOT_A_SERIES
