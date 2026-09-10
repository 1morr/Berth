"""mediainfo（plan §8.7、§1.4、brief §6.1 的第三個訊號）。

**形狀與 `fs.py` 同一種，不是 `ServiceClientFactory` 的一員**：它沒有位址、沒有憑證、
沒有連線可以握——它讀的是這台機器上的一個檔案。造一個 client 出來只會讓每個呼叫端多帶
一個沒有內容的物件。

`probe()` 是**同步**的：libmediainfo 是 C 函式庫，呼叫它的那一刻整條執行緒都在等。
背景迴圈因此以 `asyncio.to_thread` 呼叫它（`services/plan.py`）——一包 24 集的 torrent
逐檔問一次，中間不能讓 SSE 與 API 停住。

**失敗不阻擋**（plan §8.7）：讀不到、讀不懂、libmediainfo 自己爆掉，回的都是 `None`，
Plan 只少一個訊號。這一支是整條入庫路徑上唯一一個「壞了也要繼續」的相依——檔案已經
下載完了，而一份少一個訊號的 Plan 仍然入得了庫。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pymediainfo import MediaInfo

from berth.domain import MediaInfoSummary, SubtitleTrack

logger = logging.getLogger(__name__)

#: libmediainfo 的 `track_type`。字串是它的詞彙，所以只在這裡寫得出來。
_GENERAL = "General"
_VIDEO = "Video"
_AUDIO = "Audio"
_TEXT = "Text"


def probe(path: Path) -> MediaInfoSummary | None:
    """讀一個影片檔的技術規格。讀不出來就沒有答案（plan §8.7）。

    `MediaInfo.parse` 對不存在的檔案丟 `OSError`，對讀得完但不是媒體的檔案回一份只有
    General 的清單——後者由 `summarise` 判成沒有答案，兩條路殊途同歸。
    """
    try:
        media = MediaInfo.parse(str(path))
    except Exception as failure:
        # 見模組 docstring：**這一支壞了也要繼續**。檔案不在、讀不懂、libmediainfo 自己爆掉，
        # 對呼叫端都是同一件事——這個檔案沒有技術規格可以講。
        logger.warning(
            "mediainfo could not read a file", extra={"path": str(path)}, exc_info=failure
        )
        return None
    if isinstance(media, str):  # pragma: no cover —— `output=` 沒有傳，回的一定是物件。
        return None
    return summarise([track.to_data() for track in media.tracks])


def summarise(tracks: Sequence[Mapping[str, Any]]) -> MediaInfoSummary | None:
    """把 libmediainfo 的 track 清單收斂成 plan §8.7 的那幾格。

    分開一支是為了讓「它說的話怎麼讀」測得起來（`duration` 在 General 上是整數毫秒、
    在 Video 上是字串——那種事只有真的錄一份下來才知道）。
    """
    video = _first(tracks, _VIDEO)
    if video is None:
        # 沒有影像軌就沒有答案。回一份填 0 的摘要會讓「不知道多長」變成「0 秒」，
        # 而分類器拿時長把短的正片降為 extra（brief §6.2）。
        return None
    general = _first(tracks, _GENERAL) or {}
    duration = _millis(general.get("duration")) or _millis(video.get("duration"))
    return MediaInfoSummary(
        duration_s=round(duration / 1000),
        width=_int(video.get("width")),
        height=_int(video.get("height")),
        video_codec=_text(video.get("format")),
        bit_depth=_int(video.get("bit_depth")),
        audio_langs=_langs(tracks),
        subtitle_tracks=tuple(_subtitle(track) for track in _all(tracks, _TEXT)),
    )


def _subtitle(track: Mapping[str, Any]) -> SubtitleTrack:
    return SubtitleTrack(
        lang=_text(track.get("language")),
        title=_text(track.get("title")),
        # `codec_id` 是 Matroska 的那一串（`S_TEXT/UTF8`），比 `format` 精確：
        # ASS 與 SSA 的 `format` 都可能是 `ASS`，而它們的容器 id 不同。
        codec=_text(track.get("codec_id")) or _text(track.get("format")),
        forced=_flag(track.get("forced")),
        default=_flag(track.get("default")),
    )


def _langs(tracks: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """各音軌的語言，去重後保留順序（`dict` 就是保序的集合）。"""
    found = {_text(track.get("language")): None for track in _all(tracks, _AUDIO)}
    return tuple(lang for lang in found if lang)


def _first(tracks: Sequence[Mapping[str, Any]], kind: str) -> Mapping[str, Any] | None:
    return next(iter(_all(tracks, kind)), None)


def _all(tracks: Sequence[Mapping[str, Any]], kind: str) -> list[Mapping[str, Any]]:
    return [track for track in tracks if track.get("track_type") == kind]


def _millis(value: Any) -> float:
    """`duration`。實測 General 上是 `2023`（int），Video 上是 `"2000.000000"`（str）。"""
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _flag(value: Any) -> bool:
    """libmediainfo 的布林是 `"Yes"` / `"No"`。"""
    return _text(value).lower() == "yes"
