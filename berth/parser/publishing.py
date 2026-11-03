"""發佈時間對播出日的門檻：播出日比對（`parser.airing`，M3 票 14）驗證、推測虛擬季
（`parser.mapping`，M3 票 16）推測、第一批（`parser.first_batch`）擔保，三邊用同一組數字。

同一組的理由：推測說「這一輪還在播、那一集已經播了」，驗證說「那一集不在播出之前、也不比最近
播出的一集落後太多」——門檻各用一套的話，推測放進來的會被驗證擋下，或反過來。

**照字面的讀法另有一個較寬的上緣**（M5.5 票 04、brief §20.27）：地上波先行時字幕組從平台取片，
比 TMDB 的電視台日期早一週。推測虛擬季不跟著放寬：它在幾種讀法之間挑一種，窗口寬了會把前一輪
剛播完的那一集也當成剛播，兩種讀法就分不開。
"""

from __future__ import annotations

from datetime import date, timedelta

#: 發佈可以比 TMDB 的播出日早多少（使用者 2026-09-24 拍板）。TMDB 寫的是當地的播出日，發佈時間是
#: UTC：日本深夜檔在 UTC 是前一天，對岸平台與日本同步時也差一天。
RELEASE_TOLERANCE = timedelta(days=2)

#: 照字面的讀法再多容忍的地上波先行（M5.5 票 04）。ABEMA 這類平台的「地上波 1 週間先行」，正式
#: 環境量到發佈比 TMDB 早 4–8 天（深夜檔的 TMDB 日期常再晚一天），加上 `RELEASE_TOLERANCE` 共 9 天。
#: **有換算的讀法不加**：換算差一集也剛好早一週，只看日期分不開先行與算錯。
SIMULCAST_LEAD = timedelta(days=7)

#: 規則二的「早很多」，同時是「還在連載」的窗口。量測（`scripts/experiments/air_date_lag.py`，
#: 票 07 的三站 fixture 149 集 + 真的 TMDB）：28–56 天之間每一個門檻都只擋下同一筆慢發的補檔，
#: 而 split-cour 從 01 重數時對到的那一集至少落後一整個 cour（每週一集就是 10–13 週）。
#: 6 週落在兩者之間，慢幾週的字幕組不會被擋。
BEHIND_LATEST = timedelta(weeks=6)


def tolerance(*, literal: bool) -> timedelta:
    """發佈最多可以比播出日早多久：照字面的讀法多 `SIMULCAST_LEAD`。"""
    return RELEASE_TOLERANCE + SIMULCAST_LEAD if literal else RELEASE_TOLERANCE


def just_aired(aired: date, day: date, *, literal: bool = False) -> bool:
    """在 `day` 發佈的這一集是不是剛播：播出日落在發佈前 `BEHIND_LATEST` 到發佈後 `tolerance`。

    兩個窗口：推測虛擬季（`mapping._just_aired`）用預設的那一個；第一批的擔保（`first_batch`）只收
    照字面的列，用 `literal=True`，與播出日比對放行照字面的列是同一個上緣。
    """
    return -BEHIND_LATEST <= aired - day <= tolerance(literal=literal)
