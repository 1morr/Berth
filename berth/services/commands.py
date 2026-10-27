"""命令的副作用標記（brief §14「自主權看可不可以撤銷」，M3 票 05；旗標是 M5 票 02）。

每一個 service 命令標明它的副作用等級、反向命令與旗標。命令登錄表（`services/registry.py`，
M5 票 06）讀它：要不要人確認看 `needs_person`，規則只有那一份。**這裡只有標記**——不收集、不查詢，
收集在登錄表。

要給人或 AI 用的命令（非 `INTERNAL`）另外可以帶四樣，登錄表照收（`details_of`）：

- `about`：**給模型看的說明**，明寫，不從 docstring 抓（docstring 是寫給維護的人的）。
- `refusals`：它拒絕時用的理由集合（`domain` 的 `*Refusal`）。
- `validate`：**乾跑**。收 `session` 與它要的那幾格輸入（關鍵字，名字同命令的參數），只讀、不改任何
  狀態；不行就丟命令自己的拒絕例外（`reason` 在 `refusals` 裡），可以就回 `None`。命令本身走同一組
  檢查（先呼叫它，或共用它呼叫的那幾支），卡片預覽與真的執行才擋得一樣。
- `audience`：誰做得了（M5 票 07）。預設 `Role.ADMIN`；`Role.USER` 是一般使用者也行——讀取類，與
  處理自己送單的那幾支（brief §19「M5 的方向」⑦），「自己的」由命令看注入的 `user_id` 與 `role`。
  命令執行器照它擋；API 路由經執行器時門禁要與它一致（`tests/unit/test_executor_routes.py`）。

**反向命令（inverse）有三種寫法**：

1. **指名的反向命令**：`"<模組>.<函式>"`（相對 `berth.services`，同 brief §14 的
   `issues.relink`），例如 `rss.bind_series` ↔ `rss.unbind_series`。
2. **指向自己**：同一個命令換參數就能回去，例如設定類的 `set_*` 帶回原本的值。憑證類
   （`notify.set_bot_token`、`*.set_interface_login`）的原值不進 AI 的上下文，撤銷要由伺服器
   存下改之前那一份。
3. **`None`**：可逆，但沒有單一反向命令——回去要重新規劃、換別的命令，或要好幾個命令一起
   （`rss.poll_feed` 長出的紀錄、`review.confirm_audit`、`rss.set_exclusions` 這一類）。
   不可逆與只讀的一律是 `None`。

反向命令照它自己的標記走：`rss.add_feed` 的反向 `rss.delete_feed` 是不可逆的，撤銷加錯的 Feed
照樣要人確認。

寫成字串而不是函式物件，是因為反向命令常常定義在後面、或在另一個模組裡。名字寫錯、指到一個
沒標的函式，由 `tests/unit/test_command_marks.py` 擋下；標記自己矛盾的（只讀卻送單、不可逆卻有
反向命令），`CommandMark` 建出來的那一刻就丟 `ValueError`。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

from berth.domain import Role

_Command = TypeVar("_Command", bound=Callable[..., Any])

_ATTRIBUTE = "__berth_command__"
_DETAILS = "__berth_command_details__"

#: 乾跑：`session` 加上命令的幾格輸入（關鍵字）；不行就丟命令的拒絕例外。見模組 docstring。
Validator = Callable[..., Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Private:
    """標在命令輸入的一格上（`Annotated[str, PRIVATE]`）：**這一格不出伺服器**。

    確認卡存的是完整的命令輸入（執行時就用它），但 API 與給模型看的那一份由登錄表的
    `public_arguments` 去掉這幾格。例子是送單來源的下載連結：它帶著 Prowlarr 的 API key
    （M4 票 79、M5 票 13）。標在型別上而不是命令上：收同一個型別的命令都跟著遮。
    """


PRIVATE = Private()


class Effect(StrEnum):
    """副作用等級（brief §14）。"""

    #: 只讀，什麼都不改。
    READ = "read"
    #: 改了東西，但有路回去：反向命令、或同一個命令再按一次別的選項。
    REVERSIBLE = "reversible"
    #: 做了就回不去（刪 complete 裡的檔案、移除 torrent、purge）。永遠要人。
    IRREVERSIBLE = "irreversible"


class Flag(StrEnum):
    """與可不可逆無關、另外要說的事（plan §11.6〈分段〉第 1 段）。一個命令可以帶好幾個。"""

    #: 讓 Berth 連到新位址（Feed 網址、服務位址）：帶著 key 連過去是外洩 key 的唯一真實路徑。
    #: 連到已經存著的位址（輪詢既有 Feed、問 TMDB）、照作品組出已知站的網址（`rss.subscribe_*`）
    #: 不算；參數裡收任意位址的算。
    CONNECTS_OUT = "connects_out"
    #: 對外發訊息（Discord）：送出去收不回來。
    SENDS_OUT = "sends_out"
    #: 送出 torrent。受數量與磁碟閘，閘內可以不問人。
    DOWNLOADS = "downloads"
    #: 改設定：設定頁、精靈改的東西（`settings` 的分組、外部服務的設定），以及 RSS 頁上 Feed 的
    #: 設定（加刪 Feed、間隔、Route、排除條件）——使用者自己定的規則。從 Media 頁訂閱
    #: （`rss.subscribe_*`）不算：那是「要這一部」，同綁定。
    SETTINGS = "settings"
    #: 不進命令登錄表、不當 AI 的工具：背景迴圈的入口、週報產生、與別的命令同一個交易的一段
    #: （收 ORM 列的那幾支），以及**身分與門禁**——登入、登出、讀 session、Jellyfin 存取的入口
    #: 是人自己的身分，AI 不代做（M5 票 06 定）。
    INTERNAL = "internal"


#: 帶任一個就要人，不管 Effect（brief §14〈對話裡的確認卡〉）。
_PERSON_FLAGS = frozenset({Flag.CONNECTS_OUT, Flag.SENDS_OUT, Flag.SETTINGS})

#: 只讀的命令能帶的旗標：其餘幾個都在說它改了東西。
_READ_FLAGS = frozenset({Flag.CONNECTS_OUT, Flag.INTERNAL})


@dataclass(frozen=True, slots=True)
class CommandMark:
    effect: Effect
    #: 撤銷它的那一個命令，`"<模組>.<函式>"`；三種寫法見模組 docstring。
    inverse: str | None = None
    flags: frozenset[Flag] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.inverse is not None and self.effect is not Effect.REVERSIBLE:
            raise ValueError(f"a {self.effect} command has no inverse, got {self.inverse}")
        if self.effect is Effect.READ and not self.flags <= _READ_FLAGS:
            changing = sorted(self.flags - _READ_FLAGS)
            raise ValueError(f"a read command changes nothing, got flags {changing}")


@dataclass(frozen=True, slots=True)
class CommandDetails:
    """要給人或 AI 用的命令另外帶的四樣（模組 docstring）。都沒給是預設值：沒寫說明、沒列拒絕理由、
    沒有乾跑——預覽只顯示參數——只有管理員做得了。"""

    about: str = ""
    refusals: tuple[type[StrEnum], ...] = ()
    validate: Validator | None = None
    audience: Role = Role.ADMIN

    def __post_init__(self) -> None:
        if self.validate is not None and not self.refusals:
            raise ValueError("a command with validate must declare its refusals")


def command(
    effect: Effect,
    *,
    inverse: str | None = None,
    flags: Iterable[Flag] = (),
    about: str = "",
    refusals: Iterable[type[StrEnum]] = (),
    validate: Validator | None = None,
    audience: Role = Role.ADMIN,
) -> Callable[[_Command], _Command]:
    """標上副作用等級、反向命令與旗標（與登錄表要的四樣）。函式本身原樣回傳，不包一層。"""
    mark_value = CommandMark(effect=effect, inverse=inverse, flags=frozenset(flags))
    details = CommandDetails(
        about=about, refusals=tuple(refusals), validate=validate, audience=audience
    )
    if Flag.INTERNAL in mark_value.flags and details != CommandDetails():
        raise ValueError(
            "an internal command is not registered, it takes no about/refusals/validate/audience"
        )

    def mark(function: _Command) -> _Command:
        setattr(function, _ATTRIBUTE, mark_value)
        setattr(function, _DETAILS, details)
        return function

    return mark


def mark_of(function: object) -> CommandMark | None:
    """一個函式的標記；沒標的是 `None`。"""
    found = getattr(function, _ATTRIBUTE, None)
    return found if isinstance(found, CommandMark) else None


def details_of(function: object) -> CommandDetails:
    """一個命令給登錄表的四樣；沒標的是預設值。"""
    found = getattr(function, _DETAILS, None)
    return found if isinstance(found, CommandDetails) else CommandDetails()


def needs_person(mark: CommandMark) -> bool:
    """這個命令**永遠要人確認**：不可逆，或帶 `CONNECTS_OUT` / `SENDS_OUT` / `SETTINGS` 任一個。

    這是 AI 接管的邊界（M6 的開關也看它）。對話裡的確認卡範圍更大：送出 torrent、讀過外部內容
    之後帶自由文字參數的寫入也出卡（plan §11.6），那幾條看的是這一次呼叫，不只是命令。
    """
    return mark.effect is Effect.IRREVERSIBLE or not mark.flags.isdisjoint(_PERSON_FLAGS)
