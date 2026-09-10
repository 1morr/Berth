"""mediainfo adapter（plan §8.7、brief §6.2、票 11）。

**對真的檔案錄**：`tests/fixtures/mediainfo/two-second-episode.mkv` 是 ffmpeg 造出來的一份
真 Matroska——10 bit 的 AVC、兩條各自標了語言的音軌、兩條各自標了 forced / default 的字幕軌。
手寫一份假的 track 字典只會證明這一支與自己的想像一致，而 libmediainfo 說的話不歸我們想像
（`duration` 在 General 上是**整數毫秒**、在 Video 上是**字串**，這件事就是這樣發現的）。

檔案 17 KB，2 秒——它同時是「時長 < 5 分鐘的正片降為 extra」那條規則的真實輸入。
"""

from __future__ import annotations

from pathlib import Path

from berth.adapters import mediainfo

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mediainfo" / "two-second-episode.mkv"


class TestProbe:
    def test_a_real_file_answers_every_field_plan_8_7_asks_for(self) -> None:
        summary = mediainfo.probe(FIXTURE)

        assert summary is not None
        assert summary.duration_s == 2
        assert (summary.width, summary.height) == (192, 144)
        assert summary.video_codec == "AVC"
        assert summary.bit_depth == 10
        assert summary.audio_langs == ("ja", "en")

    def test_the_subtitle_tracks_keep_the_flags_that_decide_how_they_are_used(self) -> None:
        """`forced` 與 `default` 是兩件不同的事，而它們決定播放器預設開哪一條。"""
        summary = mediainfo.probe(FIXTURE)

        assert summary is not None
        tracks = [(row.lang, row.title, row.forced, row.default) for row in summary.subtitle_tracks]
        assert tracks == [("zh", "Traditional Chinese", False, True), ("en", "Signs", True, False)]
        assert all(row.codec for row in summary.subtitle_tracks)

    def test_a_file_that_is_not_there_is_not_an_answer(self, tmp_path: Path) -> None:
        """失敗不阻擋，Plan 只少一個訊號（plan §8.7）。"""
        assert mediainfo.probe(tmp_path / "never-downloaded.mkv") is None

    def test_a_file_that_is_not_a_video_is_not_an_answer(self, tmp_path: Path) -> None:
        """讀得完但裡面沒有影像軌：那不是一個「時長 0 秒的影片」，是**沒有答案**。

        分得開很重要——分類器拿時長把短的正片降為 extra，而 `0` 會讓每一個讀不出來的
        檔案都變成 extra。
        """
        not_media = tmp_path / "readme.txt"
        not_media.write_text("this is not a video", encoding="utf-8")

        assert mediainfo.probe(not_media) is None


class TestSummarise:
    def test_the_general_track_answers_the_duration_and_the_video_track_the_rest(self) -> None:
        """兩個 track 各知道一半，而它們的型別**不一樣**（實測：一個 int、一個 str）。"""
        summary = mediainfo.summarise(
            [
                {"track_type": "General", "duration": 1421000},
                {
                    "track_type": "Video",
                    "duration": "1420960.000000",
                    "width": 1920,
                    "height": 1080,
                    "format": "HEVC",
                    "bit_depth": 10,
                },
            ]
        )

        assert summary is not None
        assert summary.duration_s == 1421
        assert (summary.width, summary.height, summary.video_codec) == (1920, 1080, "HEVC")

    def test_the_video_track_answers_alone_when_the_container_does_not(self) -> None:
        summary = mediainfo.summarise(
            [{"track_type": "General"}, {"track_type": "Video", "duration": "90000"}]
        )

        assert summary is not None
        assert summary.duration_s == 90

    def test_the_same_language_twice_is_still_one_language(self) -> None:
        """雙語版常見的是「日文 + 日文評論軌」。清單回答的是「有哪些語言」。"""
        summary = mediainfo.summarise(
            [
                {"track_type": "Video"},
                {"track_type": "Audio", "language": "ja"},
                {"track_type": "Audio", "language": "ja"},
                {"track_type": "Audio", "language": "en"},
            ]
        )

        assert summary is not None
        assert summary.audio_langs == ("ja", "en")

    def test_no_video_track_is_no_answer(self) -> None:
        assert mediainfo.summarise([{"track_type": "General", "duration": 1421000}]) is None
