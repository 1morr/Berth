"""一個影片檔的技術規格摘要（plan §8.7、brief §6.1 的第三個訊號）。

住在 `domain/` 的理由與 `MediaSnapshot` 一樣，只是消費者換了一組：`adapters/mediainfo.py`
產生它、`models` 拿它當 `job_files.mediainfo_json` 的型別、`parser` 隔著 `FileEntry.duration_s`
消費它的一格——而 adapter 與 parser 依契約都只 import `domain`（plan §1.3）。

它是**下載完成之後才存在的事實**：檔名說「這是第 13 集」，mediainfo 說「這個檔案 90 秒」，
兩者不一致時後者贏（brief §6.2 的「檔名像正片但時長 90 秒 → 降為 extra」）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SubtitleTrack(BaseModel):
    """一條內封字幕軌（plan §8.7）。

    `forced` 與 `default` 分開存：一條 forced 的英文軌說的是「這一條只翻招牌」，
    而 default 說的是「播放器預設開它」——兩件事，重複版本的取捨要分得開。
    """

    model_config = ConfigDict(frozen=True)

    #: libmediainfo 報的語言碼（實測是兩碼的 `ja` / `en` / `zh`）。原樣存，不翻譯成
    #: `Lang`——那個 enum 是**檔名 token** 的詞彙表（brief §6.8），繁簡在這裡分不出來。
    lang: str = ""
    #: 軌道標題。中文字幕組常常把繁簡寫在這裡（`繁體中文`），而語言碼一律是 `zh`。
    title: str = ""
    codec: str = ""
    forced: bool = False
    default: bool = False


class MediaInfoSummary(BaseModel):
    """`probe()` 的結果（plan §8.7）。

    **只有真的讀到影像軌才會有一份**：讀不出來時呼叫端拿到的是 `None` 而不是一份填 0 的
    摘要——`duration_s == 0` 與「不知道多長」是兩件事，而分類器拿時長做判斷（brief §6.2）。
    """

    model_config = ConfigDict(frozen=True)

    #: 秒。容器說的優先，容器沒說才問影像軌（實測 Matroska 兩邊差 23 毫秒）。
    duration_s: int = 0
    width: int = 0
    height: int = 0
    #: libmediainfo 的 `format`（`AVC` / `HEVC`）。不是檔名裡的 `x265`。
    video_codec: str = ""
    bit_depth: int = 0
    #: 各音軌的語言，去重後保留順序。「有哪些語言」是問題，「有幾條軌」不是。
    audio_langs: tuple[str, ...] = ()
    subtitle_tracks: tuple[SubtitleTrack, ...] = ()
