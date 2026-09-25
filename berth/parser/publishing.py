"""發佈時間對播出日的兩個門檻：播出日比對（`parser.airing`，M3 票 14）驗證、推測虛擬季
（`parser.mapping`，M3 票 16）推測，兩邊用同一組數字。

同一組的理由：推測說「這一輪還在播、那一集已經播了」，驗證說「那一集不在播出之前、也不比最近
播出的一集落後太多」——門檻各用一套的話，推測放進來的會被驗證擋下，或反過來。
"""

from __future__ import annotations

from datetime import timedelta

#: 發佈可以比 TMDB 的播出日早多少（使用者 2026-09-24 拍板）。TMDB 寫的是當地的播出日，發佈時間是
#: UTC：日本深夜檔在 UTC 是前一天，對岸平台與日本同步時也差一天。
RELEASE_TOLERANCE = timedelta(days=2)

#: 規則二的「早很多」，同時是「還在連載」的窗口。量測（`scripts/experiments/air_date_lag.py`，
#: 票 07 的三站 fixture 149 集 + 真的 TMDB）：28–56 天之間每一個門檻都只擋下同一筆慢發的補檔，
#: 而 split-cour 從 01 重數時對到的那一集至少落後一整個 cour（每週一集就是 10–13 週）。
#: 6 週落在兩者之間，慢幾週的字幕組不會被擋。
BEHIND_LATEST = timedelta(weeks=6)
