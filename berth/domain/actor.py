"""誰在做這件事：`events.actor` 的寫法與命令執行器的角色（plan §2.3、M5 票 07，研究 R14）。

`events.actor` 是一格字串，寫法只有這裡一份：

- 人：他的 user id（`"3"`）。
- `system`：背景迴圈、對帳、沒有人按的那些。
- `rss:<ref>`：RSS Series 送的單（`ref` 是 Job 的 `trigger_ref`，`rss_label`）。
- `ai:<user id>`：AI **替誰**做的（使用者在側面板叫它做事）。替誰做與做的是誰同一格說完，
  寫法同 `rss:<ref>`。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from berth.domain.enums import Role

SYSTEM = "system"


class ActorKind(StrEnum):
    """經命令執行器的那幾種。RSS 送單不經執行器，它的寫法只有 `rss_label`。"""

    PERSON = "person"
    SYSTEM = "system"
    AI = "ai"


@dataclass(frozen=True, slots=True)
class Actor:
    """執行器收的那一個：是誰、替誰、能做什麼。用下面的建構式，不直接建。"""

    kind: ActorKind
    #: 人是他自己；AI 是它替誰做；`system` 沒有人。
    user_id: int | None
    #: 能做的範圍。人與 AI 是那個人的角色；`system` 是背景迴圈，不受角色限制。
    role: Role

    @classmethod
    def person(cls, user_id: int, role: Role) -> Actor:
        return cls(ActorKind.PERSON, user_id, role)

    @classmethod
    def ai(cls, on_behalf_of: int, role: Role) -> Actor:
        """AI 替 `on_behalf_of` 做事：角色照那個人，碰得到的也只有他碰得到的。"""
        return cls(ActorKind.AI, on_behalf_of, role)

    @property
    def label(self) -> str:
        """寫進 `events.actor` 的那一格（模組 docstring）。"""
        if self.kind is ActorKind.AI:
            return f"{ActorKind.AI}:{self.user_id}"
        return label_of(self.user_id)


SYSTEM_ACTOR = Actor(ActorKind.SYSTEM, None, Role.ADMIN)


def label_of(user_id: int | None) -> str:
    """按的人的 `events.actor`；沒有人就是 `system`。"""
    return str(user_id) if user_id is not None else SYSTEM


def rss_label(ref: str) -> str:
    return f"rss:{ref}"


def owner_of(label: str) -> int | None:
    """`events.actor` 背後的那個人：人是他、AI 是它替的那個人；`system` 與 RSS 沒有。"""
    person = label.removeprefix(f"{ActorKind.AI}:")
    return int(person) if person.isdigit() else None
