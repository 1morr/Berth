"""「下載停滯」（`domain.stalled`，M5.5 票 12）：`WhyNot` 把停滯併進「在路上」，追更頁拆出來說。"""

from __future__ import annotations

from berth.domain import EpisodeFacts, FeedItemStatus, JobState, WhyNot, conclude, stalled


def facts(
    *jobs: JobState, items: frozenset[FeedItemStatus] = frozenset(), imported: bool = False
) -> EpisodeFacts:
    return EpisodeFacts(
        imported=imported,
        in_jellyfin=False,
        jobs=frozenset(jobs),
        items=items,
        send_rejected=False,
        aired=True,
    )


class TestStalled:
    def test_only_a_stalled_download_on_the_way_is_stalled(self) -> None:
        one = facts(JobState.STALLED)
        assert conclude(one) is WhyNot.DOWNLOADING
        assert stalled(one)

    def test_another_download_still_moving_is_not(self) -> None:
        assert not stalled(facts(JobState.STALLED, JobState.DOWNLOADING))

    def test_an_item_sent_next_round_is_not(self) -> None:
        assert not stalled(facts(JobState.STALLED, items=frozenset({FeedItemStatus.MATCHED})))

    def test_a_conclusion_ahead_of_downloading_speaks_instead(self) -> None:
        assert not stalled(facts(JobState.STALLED, JobState.IMPORT_FAILED))
        assert not stalled(facts(JobState.STALLED, imported=True))

    def test_nothing_on_the_way_is_not(self) -> None:
        assert not stalled(facts())
        assert not stalled(facts(JobState.DOWNLOADING))
