"""側面板防護裡不靠模型的幾塊（M5 票 20、研究 C3）：乒乓與無進展、工具結果截斷、provider 斷路器。

**乒乓與無進展**（`Progress`）：每次有結果的工具呼叫記下（呼叫、結果的雜湊），模型再被叫之前
看上一段：最後四次是 A-B-A-B 而結果都沒變是乒乓；連續幾段都沒有沒看過的（呼叫、結果）是無進展。
「狀態」是這一輪看過的結果：M5 的工具都是讀取類，Berth 看得到世界變了沒只有從結果。被擋下的
呼叫算沒有新東西；失敗的不算數（同重複呼叫：失敗後重試是正當的）。

**斷路器**（`ProviderBreaker`，plan §11.6〈防護〉）：同一份 provider 設定（接口、網址、模型、
key）的模型呼叫連續失敗 5 次，暫停 15 分鐘——期間開不了新的一輪（`ai_paused`），側面板照
`GET /agent/status` 說明。時間到了放一輪過去試：再失敗就再暫停 15 分鐘，成功就從 0 數起。換了
key 或模型是另一份設定，不必等。只算 provider 的失敗（`pydantic_ai.exceptions.ModelAPIError`：
HTTP 錯、連不上、key 被拒），模型回了怪東西、使用者按了停止不算。狀態在程序裡（重啟就清掉）：
它擋的是失控的重試，不是要記住的事。M6 的背景任務看同一份，暫停期間退回沒有 AI 的行為
（brief §6.10）。

**截斷**（`clip`）：一筆工具結果交給模型之前量它的 JSON 長度，超過上限就從最大的那一段砍起——
清單留前面一半、長字串留前面一半——直到放得下；每一處砍了多少記成 `Cut`，模型看得到「這裡只給了
5 筆，還有 15 筆」，可以自己換頁或縮小範圍再問。砍不下來的（上千個 key 的物件）整份換成一段文字
預覽。
長度以字元算：中日文一個字差不多一個 token，英文四個字元一個，上限照前者抓。
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, NamedTuple

from berth.adapters.ai import AiEndpoint
from berth.domain import AiStopReason
from berth.models.types import utcnow


class _Seen(NamedTuple):
    """一次有結果的工具呼叫。"""

    call: str
    digest: str


@dataclass
class Progress:
    """一輪裡工具帶來了什麼（`Turn.progress`）。"""

    _trail: list[_Seen] = field(default_factory=list)
    #: 上一次模型呼叫之後這一段有沒有沒看過的結果；`None` 是這一段沒有算數的呼叫。
    _news: bool | None = None
    #: 連續幾段沒有新結果。
    _stale: int = 0

    def saw(self, call: str, result: object) -> None:
        """一次有結果的呼叫（`call` 是工具與參數）。"""
        seen = _Seen(call, _digest(result))
        new = seen not in self._trail
        self._trail.append(seen)
        self._news = bool(self._news) or new

    def blocked(self) -> None:
        """一次被擋下的呼叫：沒有新東西。"""
        self._news = bool(self._news)

    def verdict(self, stale_steps: int) -> AiStopReason | None:
        """模型再被叫一次之前：收掉上一段，回該不該停、為什麼。"""
        if self._news is not None:
            self._stale = 0 if self._news else self._stale + 1
            self._news = None
        if _back_and_forth(self._trail):
            return AiStopReason.PING_PONG
        if self._stale >= stale_steps:
            return AiStopReason.NO_PROGRESS
        return None


def _digest(result: object) -> str:
    text = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _back_and_forth(trail: Sequence[_Seen]) -> bool:
    """最後四次是 A-B-A-B（A 與 B 不同），而 A、B 第二次的結果與第一次一樣。"""
    if len(trail) < 4:
        return False
    a1, b1, a2, b2 = trail[-4:]
    return a1 == a2 and b1 == b2 and a1.call != b1.call


#: 砍字串時至少留這麼多字：再短的字串砍了也省不了多少。
_MIN_TEXT = 80


@dataclass(frozen=True, slots=True)
class Cut:
    """一處被砍掉的：`at` 是路徑（`items`、`[0].files`；整份是 `$`）。"""

    at: str
    shown: int
    more: int
    unit: Literal["items", "chars"] = "items"


@dataclass(frozen=True, slots=True)
class Clipped:
    value: object
    #: 沒砍是空的。
    cuts: tuple[Cut, ...]


#: 一處可以砍的：所在的容器與它在容器裡的 key。
type _Slot = tuple[list[object], int] | tuple[dict[str, object], str]


def _size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _get(slot: _Slot) -> object:
    container, key = slot
    return container[key]  # type: ignore[index]  # `_Slot` 的兩種配對裡 key 一定合容器的型別


def _put(slot: _Slot, value: object) -> None:
    container, key = slot
    container[key] = value  # type: ignore[index]  # 同上


def _path(parent: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{parent}[{key}]"
    return f"{parent}.{key}" if parent else key


def _slots(value: object, at: str = "") -> Iterator[tuple[str, _Slot]]:
    """每一個可以砍的地方（清單、長字串）與它的路徑，深的先。"""
    slots: list[_Slot]
    if isinstance(value, dict):
        slots = [(value, key) for key in value]
    elif isinstance(value, list):
        slots = [(value, index) for index in range(len(value))]
    else:
        return
    for slot in slots:
        child, here = _get(slot), _path(at, slot[1])
        yield from _slots(child, here)
        if (isinstance(child, list) and len(child) > 1) or (
            isinstance(child, str) and len(child) > _MIN_TEXT
        ):
            yield here, slot


def _shown(at: str) -> str:
    """`$.items` → `items`、`$[0].files` → `[0].files`；整份是 `$`。"""
    if at.startswith("$."):
        return at[2:]
    if at.startswith("$["):
        return at[1:]
    return at


def clip(value: object, limit: int) -> Clipped:
    """`value` 的 JSON 放得進 `limit` 個字元就原樣回；放不下就砍（不動傳進來的那一份）。"""
    if _size(value) <= limit:
        return Clipped(value, ())
    # 整份包一層，最外層是清單或字串時也有容器可以砍。
    root: dict[str, object] = {"$": copy.deepcopy(value)}
    #: 路徑 → 砍之前多長、砍到哪一處。
    cut: dict[str, tuple[int, _Slot]] = {}
    while _size(root["$"]) > limit:
        found = list(_slots(root))
        if not found:
            break
        at, slot = max(found, key=lambda item: _size(_get(item[1])))
        target = _get(slot)
        assert isinstance(target, (list, str))
        cut.setdefault(at, (len(target), slot))
        floor = 1 if isinstance(target, list) else _MIN_TEXT
        _put(slot, target[: max(floor, len(target) // 2)])
    if _size(root["$"]) > limit:
        return _preview(value, limit)
    cuts = []
    for at, (total, slot) in cut.items():
        kept = _get(slot)
        assert isinstance(kept, (list, str))
        unit: Literal["items", "chars"] = "items" if isinstance(kept, list) else "chars"
        cuts.append(Cut(at=_shown(at), shown=len(kept), more=total - len(kept), unit=unit))
    return Clipped(root["$"], tuple(cuts))


def _preview(value: object, limit: int) -> Clipped:
    """砍不下來的：整份的 JSON 換成一段放得下的文字。"""
    text = json.dumps(value, ensure_ascii=False, default=str)
    # 預覽本身也要序列化成 JSON 字串：引號與跳脫字元也算。
    preview = text[: max(0, limit - 2)]
    while preview and _size(preview) > limit:
        preview = preview[: len(preview) * 9 // 10]
    cut = Cut(at="$", shown=len(preview), more=len(text) - len(preview), unit="chars")
    return Clipped(preview, (cut,))


@dataclass(slots=True)
class _Tally:
    #: 連續失敗幾次；成功歸 0。暫停結束不歸 0，所以放過去試的那一輪再失敗就馬上再暫停。
    failures: int = 0
    paused_until: datetime | None = None
    #: 讓它暫停的那一次的錯誤原文（key 已遮掉）。
    error: str = ""


@dataclass(frozen=True, slots=True)
class Pause:
    until: datetime
    #: 讓它暫停的那一次的錯誤原文（key 已遮掉）。
    error: str


@dataclass
class ProviderBreaker:
    """一個程序一份（`AgentRuntime.breaker`）。"""

    threshold: int = 5
    pause: timedelta = timedelta(minutes=15)
    now: Callable[[], datetime] = utcnow
    _tallies: dict[str, _Tally] = field(default_factory=dict)

    def paused(self, endpoint: AiEndpoint) -> Pause | None:
        """還在暫停就回到什麼時候、為什麼；沒有暫停是 `None`。"""
        tally = self._tallies.get(_key(endpoint))
        if tally is None or tally.paused_until is None or tally.paused_until <= self.now():
            return None
        return Pause(tally.paused_until, tally.error)

    def failed(self, endpoint: AiEndpoint, error: str) -> bool:
        """記一次失敗（`error` 是遮過 key 的原文）；回 `True` 是這一次讓它暫停了。"""
        tally = self._tallies.setdefault(_key(endpoint), _Tally())
        tally.failures += 1
        if tally.failures < self.threshold:
            return False
        tally.paused_until = self.now() + self.pause
        tally.error = error
        return True

    def succeeded(self, endpoint: AiEndpoint) -> None:
        self._tallies.pop(_key(endpoint), None)


def _key(endpoint: AiEndpoint) -> str:
    """一份 provider 設定。雜湊過：key 不必多存一份在記憶體的另一處。"""
    raw = "\n".join((endpoint.provider, endpoint.base_url, endpoint.model, endpoint.api_key))
    return hashlib.sha256(raw.encode()).hexdigest()
