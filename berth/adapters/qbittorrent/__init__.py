"""qBittorrent adapter（plan §8.1）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from berth.adapters.http import AuthFailedError, ServiceError

#: 支援下限（brief §16.4）。低於它的 Web API 缺少 Berth 要用的端點，精靈拒絕接入。
MIN_WEBAPI = (2, 8, 4)

#: `torrents/add` 改用 `stopped` 的那一版。實測 4.4.5（2.8.5）只認 `paused`、
#: 5.2.3（2.15.1）只認 `stopped`，送錯的那個**被靜默忽略**，torrent 就開始下載（brief §20.7）。
STOPPED_SINCE_WEBAPI = (2, 11)


class TorrentRejectedError(ServiceError):
    """qBittorrent 答話了，而它不收這一個 torrent。

    2026-09-10 對 5.2.3 實測到兩種：`409 Conflict`（已經有同一個 hash，或 category 的
    save path 用不了）與 `415`（那份 `.torrent` 不是有效的 torrent，body 帶檔名與原因）。

    與「連不上」分開的理由是**下一步不同**：這一個重試一百次多半還是一樣，而連不上
    只要等服務回來。畫面上兩種都是 `submit_failed`，但原文說得出是哪一種（plan §3.1）。
    """


#: 連續登入失敗之後 qBittorrent 封住來源 IP 時，`auth/login` 回的那一句（**4.4.5 與 5.2.3
#: 實測同一句**，都是第 6 次失敗開始，狀態碼 `403`）。比對用小寫子字串而不是整句相等：
#: 那句話的措辭在版本之間可能改，而「banned」這個字是它與 `Forbidden` 的差別所在。
BAN_MARKER = "has been banned"


class IpBannedError(AuthFailedError):
    """qBittorrent 把 Berth 這台的 IP 封了（plan §8.1、T1.9 第四條）。

    2026-09-10 對 4.4.5 與 5.2.3 各實測一輪：連續 5 次帳密錯之後，第 6 次的
    `auth/login` 回 `403` + `Your IP address has been banned after too many failed
    authentication attempts.`。**帳密錯本身不是 403**——4.4.5 是 `200` + `Fails.`，
    5.2.3 是 `401`，所以登入端點上的 403 只有這一個意思。

    是 `AuthFailedError` 的子類，因為對「還連不連得上」這個問題兩者的答案一樣；分出來是
    因為**下一步不同**：帳密不對要去改設定，被封要等封鎖過期（預設 1 小時）或去 qBittorrent
    的介面上解除，改帳密一點用都沒有。

    被封之後其他端點回的是 `403` + `Forbidden`——與「沒有登入」一模一樣，分不出來
    （實測）。所以這個判定只有登入那一支做得到。
    """


@dataclass(frozen=True, slots=True)
class QbittorrentVersion:
    """`app/version` 與 `app/webapiVersion`。

    版本判斷是必要條件不是最佳化：送錯 `paused` / `stopped` 會被靜默忽略（brief §20.7）。
    """

    app: str
    webapi: str

    @property
    def supported(self) -> bool:
        return _parse(self.webapi) >= MIN_WEBAPI

    @property
    def pause_parameter(self) -> str:
        """加入 torrent 時要送的那個「先別下載」參數。"""
        return "stopped" if _parse(self.webapi) >= STOPPED_SINCE_WEBAPI else "paused"

    @property
    def start_endpoint(self) -> str:
        """讓一個 torrent 重新開始的那一支。**同一次改名**：5.0（Web API 2.11）把
        `torrents/resume` 改成 `torrents/start`，與 `paused` → `stopped` 是同一版（brief §20.2）。
        """
        return (
            "torrents/start" if _parse(self.webapi) >= STOPPED_SINCE_WEBAPI else "torrents/resume"
        )


#: 每一筆 Berth 送出去的 torrent 都掛這個 tag（plan §8.1）。它讓使用者在 qBittorrent 自己的
#: 介面上分得出「這是 Berth 放的」，也讓票 10 的 poller 有一個 category 之外的第二道篩子。
BERTH_TAG = "berth"

#: `Original` = 照 torrent 自己的結構存（brief §20.7 實測四種組合，`torrents/files[].name`
#: 一律相對 `save_path`）。改成別的會讓解析器看到的路徑與做種中的檔案佈局不一樣。
CONTENT_LAYOUT = "Original"


@dataclass(frozen=True, slots=True)
class TorrentAdd:
    """要加進 qBittorrent 的一份。

    `magnet` 與 `content` 剛好有一個（`adapters.torrent.TorrentSource` 的同一個分岔）：
    前者是表單值，後者是 multipart 的檔案欄位，兩邊在 `torrents/add` 上不是同一種東西。
    """

    #: `<route.category>`。save path 由它決定，因為 `autoTMM=true`（brief §4.1）。
    category: str
    magnet: str = ""
    content: bytes = b""
    filename: str = "berth.torrent"


def add_form(request: TorrentAdd, version: QbittorrentVersion) -> dict[str, str]:
    """`torrents/add` 的表單值（不含 `.torrent` 那個檔案欄位）。

    抽出來是因為**版本矩陣要測得到**：`paused` / `stopped` 選錯的那一半不會報錯，
    只會靜默地做相反的事（brief §20.7），所以那個選擇要有一個看得見、驗得了的形狀。

    `savepath` 刻意不送：`autoTMM=true` 時路徑由 category 決定，兩個來源會讓「這個 torrent
    存到哪裡」有兩個答案，而其中一個會在使用者改 category 時悄悄過期。
    """
    form = {
        "category": request.category,
        "tags": BERTH_TAG,
        "contentLayout": CONTENT_LAYOUT,
        "autoTMM": "true",
        # **明講「開始下載」**：qBittorrent 有一個「加入後不自動開始」的全域偏好，而
        # plan §3.1 的狀態機假設送出去的 torrent 會自己走到 `metadata_ready`。
        version.pause_parameter: "false",
    }
    if request.magnet:
        form["urls"] = request.magnet
    return form


#: `torrents/files` 的 `priority`。`0` 是「不下載」，那種檔案不進 Plan（brief §5.1）。
PRIORITY_SKIP = 0


@dataclass(frozen=True, slots=True)
class TorrentFile:
    """`torrents/files` 的一列（brief §20.2）。"""

    index: int
    #: **相對 `save_path`，含 torrent 自己的根目錄那一層**（brief §20.7；2026-09-10 對 4.4.5
    #: 與 5.2.3 各再驗一次多檔的情形，兩版都是
    #: `Berth.Poller.Test.S01.1080p.WEB-DL/Subs/….srt`）。
    name: str
    size: int
    priority: int
    progress: float

    @property
    def wanted(self) -> bool:
        return self.priority != PRIORITY_SKIP


#: 搬檔與校驗中的 state 前綴。從 temp path 搬到 save path 期間是 `moving`，此時檔案不在
#: save path 上，判成完成會讓 importer 對著半個檔案建硬鏈接（brief §20.2）。
SETTLING_STATES = ("moving", "checking")

#: 「還在跟 DHT 要 metadata」。這個狀態下 `torrents/files` 回的是空陣列（實測兩版皆然），
#: 所以它就是 plan §3.1 那條「state 不是 `metaDL`」的來源。
METADATA_PENDING_STATE = "metaDL"

#: 「有種可連但沒有資料在動」。plan §3.1 的 `stalled` 由它加上一段時間決定。
STALLED_STATE = "stalledDL"

#: 客戶端自己回報的兩種壞掉。`missingFiles` 是檔案不見了，`error` 是它自己說不出話。
MISSING_FILES_STATE = "missingFiles"
ERROR_STATE = "error"


@dataclass(frozen=True, slots=True)
class TorrentStatus:
    """`sync/maindata` 裡一個 torrent 的樣子，只留 Berth 讀得到的那幾欄。

    **不翻譯成 `JobState`**：那是 `services` 的判斷（plan §3.1 的轉換表），而這一層的職責
    是忠實翻譯協定。這裡只提供三個「協定自己回答得了」的述詞。
    """

    hash: str
    name: str
    #: qBittorrent 自己的狀態字串（`stalledDL`、`pausedUP`…），原樣。
    state: str
    category: str
    tags: tuple[str, ...]
    #: 0.0–1.0。
    progress: float
    #: 完成的 unix 秒。**未完成時 4.4.5 是 `0`、5.2.3 是 `-1`**（2026-09-10 實測），
    #: 所以判定寫成 `> 0` 而不是 `!= 0`。
    completion_on: int
    #: 上一次真的有資料在動。`stalled` 的「超過 N 分鐘」量的就是它——這個數字是
    #: qBittorrent 自己的量測，Berth 不必另存一個「什麼時候變成 stalledDL 的」。
    last_activity: int
    added_on: int
    save_path: str
    content_path: str
    total_size: int

    @property
    def metadata_ready(self) -> bool:
        """metadata 拿到了沒（plan §3.1 的「state 不是 `metaDL`」）。"""
        return self.state != METADATA_PENDING_STATE

    @property
    def settling(self) -> bool:
        """搬檔或校驗中。這時候的 `progress == 1` 不算完成（brief §20.2）。"""
        return self.state.startswith(SETTLING_STATES)

    @property
    def complete(self) -> bool:
        """brief §5.1 的完成判定裡**客戶端答得出來的那三條**。

        第四條（每個檔案真的在 save path 底下 `stat` 得到）要碰檔案系統，所以它在
        `services` 那一層，不在協定翻譯這一層。
        """
        return self.progress >= 1.0 and self.completion_on > 0 and not self.settling

    @property
    def idle(self) -> bool:
        return self.state == STALLED_STATE

    @property
    def idle_since(self) -> int:
        """從什麼時候開始沒有動靜。`last_activity` 沒有值時退回加入時間。"""
        return self.last_activity if self.last_activity > 0 else self.added_on


def parse_status(info_hash: str, row: Mapping[str, Any]) -> TorrentStatus:
    """`sync/maindata` 的 `torrents[hash]` → `TorrentStatus`。

    每一欄都給預設值：**增量那一輪只帶變動的欄位**（實測 5.2.3 的一輪只有
    `{"num_leechs", "time_active"}`），所以呼叫端一定要先把增量併回完整的那一份再進來。
    合併是 `MaindataCursor` 的事，這裡只負責把併好的 dict 讀成型別。
    """
    return TorrentStatus(
        hash=info_hash,
        name=str(row.get("name", "")),
        state=str(row.get("state", "")),
        category=str(row.get("category", "")),
        # qBittorrent 的 `tags` 是一個逗號分隔的字串，不是陣列。
        tags=tuple(tag.strip() for tag in str(row.get("tags", "")).split(",") if tag.strip()),
        progress=float(row.get("progress", 0.0) or 0.0),
        completion_on=int(row.get("completion_on", 0) or 0),
        last_activity=int(row.get("last_activity", 0) or 0),
        added_on=int(row.get("added_on", 0) or 0),
        save_path=str(row.get("save_path", "")),
        content_path=str(row.get("content_path", "")),
        total_size=int(row.get("total_size", 0) or 0),
    )


class MaindataCursor:
    """`sync/maindata` 的 `rid` 與它的增量合併（brief §20.2）。

    協定是「你上次拿到 rid N，我只告訴你之後變了什麼」，所以**合併在這一層**：一輪增量
    裡一個 torrent 可能只帶 `{"num_leechs": 2}`，直接讀它會得到一個沒有 category、沒有
    state 的空殼。合併之後 `torrents()` 永遠是**客戶端當下的完整清單**——`client_removed`
    因此不必看 `torrents_removed`，「不在這份清單裡」就是答案，重啟後的第一輪也成立。

    一個 cursor 對一個 HTTP session：**rid 的狀態在 qBittorrent 那邊是掛在 SID 上的**
    （2026-09-10 實測：不帶 cookie 的話每一輪都回 `full_update: true`），所以換了 client
    就等於重新開始，而重新開始就是一次全量——兩邊自然對齊。
    """

    def __init__(self) -> None:
        self._rid = 0
        self._rows: dict[str, dict[str, Any]] = {}

    @property
    def rid(self) -> int:
        return self._rid

    def apply(self, payload: Mapping[str, Any]) -> tuple[TorrentStatus, ...]:
        """吃一輪回應，回傳合併之後的完整清單。"""
        self._rid = int(payload.get("rid", self._rid) or 0)
        if payload.get("full_update"):
            self._rows = {}
        rows = payload.get("torrents")
        if isinstance(rows, Mapping):
            for info_hash, changed in rows.items():
                if isinstance(changed, Mapping):
                    self._rows.setdefault(str(info_hash), {}).update(changed)
        removed = payload.get("torrents_removed")
        if isinstance(removed, list):
            for info_hash in removed:
                self._rows.pop(str(info_hash), None)
        return tuple(parse_status(key, value) for key, value in self._rows.items())


@dataclass(frozen=True, slots=True)
class QbittorrentCategory:
    """`torrents/categories` 的一列。"""

    name: str
    save_path: str


@dataclass(frozen=True, slots=True)
class CategoryOutcome:
    """`ensure_category` 的結果。`save_path` 一律是**那台 qBittorrent 現在的值**。"""

    name: str
    save_path: str
    #: 這一次建的。已經在那裡的話是 False，重跑精靈時大部分是這樣。
    created: bool
    #: 同名的 category 已存在，但指向別的 save path。Berth 不覆寫它。
    conflict: bool


class QbittorrentClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def login(self, username: str, password: str) -> None:
        """帳密不對時丟 `AuthFailedError`。免密的套件內服務不需要呼叫。"""
        ...

    async def version(self) -> QbittorrentVersion: ...

    async def preferences(self) -> Mapping[str, Any]:
        """`app/preferences`。精靈第 4 步拿它與建議值比對（plan §8.1）。"""
        ...

    async def set_preferences(self, values: Mapping[str, Any]) -> None:
        """`app/setPreferences`。只送要改的鍵，其餘不動。"""
        ...

    async def categories(self) -> tuple[QbittorrentCategory, ...]: ...

    async def add_torrent(self, request: TorrentAdd) -> None:
        """`torrents/add`。qBittorrent 不收就丟 `ServiceError` 的子類。

        版本判斷在**實作裡**而不是呼叫端：它要讀 `app/webapiVersion`，而那是這一層的事
        （plan §8.1）。呼叫端只說「加這一個」，不必記得哪一版叫什麼。
        """
        ...

    async def delete_torrent(self, info_hash: str, *, delete_files: bool) -> None:
        """`torrents/delete`。刪除範圍的「從 qBittorrent 移除 torrent」那一個旗標（brief §9.2）。

        **它沒有這個 hash 也是成功**（實測原始碼 `applyToTorrents` 直接跳過，brief §20.2）：
        torrent 早就被人在 qBittorrent 介面上刪掉的那一筆，這裡照樣走得完。
        """
        ...

    async def recheck(self, info_hash: str) -> None:
        """`torrents/recheck`：重新校驗磁碟上的資料（`missing_files` 的「重新 recheck」）。

        **不認得的 hash 也是成功**（brief §20.2）：那一筆在這中間被人拿掉的話，下一輪
        poller 看到的就是 `client_removed`，不必在這裡先問一次。
        """
        ...

    async def start(self, info_hash: str) -> None:
        """讓一個 torrent 重新開始（4.x 的 `torrents/resume`、5.x 的 `torrents/start`）。

        它也清掉客戶端自己的錯誤狀態（`client_error` 的「重試」）。版本判斷在實作裡，同
        `add_torrent`。
        """
        ...

    async def create_category(self, name: str, save_path: str) -> None:
        """`torrents/createCategory`。同名的已經存在時回 409（實測原始碼的
        `Unable to create category`），所以呼叫端要先讀再建——`ensure_category` 做這件事。
        """
        ...

    async def sync(self) -> tuple[TorrentStatus, ...]:
        """自上次以來變了什麼，合併之後的**完整清單**（`sync/maindata`，plan §3.2）。

        `rid` 由實作自己記著：它是這條連線的狀態，而 qBittorrent 那邊也把它掛在 SID 上
        （實測）。呼叫端只問「現在客戶端裡有哪些 torrent」，換一個 client 就是重新開始。
        """
        ...

    async def files(self, info_hash: str) -> tuple[TorrentFile, ...]:
        """`torrents/files`。metadata 還沒到時回空 tuple（實測兩版都是 `200` + `[]`）。"""
        ...

    async def aclose(self) -> None: ...


async def ensure_category(client: QbittorrentClient, name: str, save_path: str) -> CategoryOutcome:
    """一個 Route 的 category：不存在才建，存在但 save path 不同就回報衝突（plan §8.1）。

    **衝突不覆寫**：autoTMM 開著時改 category 的 savePath 會自動搬走該分類的所有 torrent
    （brief §20.2），那是使用者自己的資料。畫面把兩個路徑並排，讓他自己決定。

    比對前正規化尾斜線：4.4 把設進去的 `/data/x` 讀回來寫成 `/data/x/`（brief §20.7），
    照字面比會讓每次重跑都判成衝突。
    """
    existing = next((row for row in await client.categories() if row.name == name), None)
    if existing is None:
        await client.create_category(name, save_path)
        return CategoryOutcome(name=name, save_path=save_path, created=True, conflict=False)
    return CategoryOutcome(
        name=name,
        save_path=existing.save_path,
        created=False,
        conflict=_normalise(existing.save_path) != _normalise(save_path),
    )


def _normalise(path: str) -> str:
    return path.rstrip("/") or "/"


def _parse(version: str) -> tuple[int, ...]:
    """`2.8.5` → `(2, 8, 5)`。認不得的字串當成 0，也就是「太舊」。"""
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = "".join(char for char in chunk if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


__all__ = [
    "BAN_MARKER",
    "BERTH_TAG",
    "CONTENT_LAYOUT",
    "ERROR_STATE",
    "METADATA_PENDING_STATE",
    "MIN_WEBAPI",
    "MISSING_FILES_STATE",
    "PRIORITY_SKIP",
    "SETTLING_STATES",
    "STALLED_STATE",
    "STOPPED_SINCE_WEBAPI",
    "CategoryOutcome",
    "IpBannedError",
    "MaindataCursor",
    "QbittorrentCategory",
    "QbittorrentClient",
    "QbittorrentVersion",
    "TorrentAdd",
    "TorrentFile",
    "TorrentRejectedError",
    "TorrentStatus",
    "add_form",
    "ensure_category",
    "parse_status",
]
