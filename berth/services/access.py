"""誰進得了哪一條路徑：`/api` 門禁與 AI 工具共用的那一份規則（plan §6）。

M5 票 06 從 `api/gate.py` 搬來。

門禁（`api/gate.py`）照它放行或擋下請求；命令登錄表（`services/registry.py`）照它決定一個使用者
拿得到哪些工具——每一個工具指著做同一件事的那一支端點，兩邊問的是同一張表，模型那一邊沒有
第二份。這裡只看方法、路徑與角色，沒有 IO：擁有者成立了沒、session 是誰，是門禁自己的事。
"""

from __future__ import annotations

from enum import StrEnum

from berth.domain import Role

#: 匿名可達的端點，路徑相對於 `/api`（plan §6）。
ANONYMOUS_PATHS = frozenset(
    {
        #: 監控與 compose 的健康檢查要打得到，而且只回 ok / degraded 與精靈跑完了沒。
        "/health",
        "/auth/login",
        #: 登出永遠成功：session 已經過期的人也該把 cookie 清掉。
        "/auth/logout",
    }
)

#: 設定精靈。它自己有一條隨時間關上的規則，見 `api/gate._setup_verdict`。
SETUP_PREFIX = "/setup"

#: 精靈的開場：擁有者成立之前匿名可達的那幾支（M4 票 06、15）。只有「選 Jellyfin、測它」與
#: 「成為擁有者」——其餘的精靈端點會寫別人的服務（建管理員之外的一切、套用偏好、加站），要在門後。
#: 擁有者成立之後它們與其他精靈端點一樣只有管理員。`(方法, 路徑)`，完全比對。
SETUP_OPENING_PATHS: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/setup/status"),
        # 只查套件內的主機名（M4 票 30）：頁 1 的 Jellyfin 卡片要用，什麼都不寫、不連任何服務。
        ("GET", "/setup/compose"),
        ("POST", "/setup/services/jellyfin"),
        ("POST", "/setup/services/jellyfin/test"),
        ("POST", "/setup/owner"),
        # 既有 Jellyfin 的連線並登入（M4 票 67）：上面兩支（選、成為擁有者）合成一次。
        ("POST", "/setup/owner/existing"),
    }
)

#: 只有管理員進得來的路徑（brief §11）。規則放在門禁而不是 router 的相依，理由與 `setup/*`
#: 一樣：底下新掛的端點什麼都不做就已經在同一道門後面。
#:
#: Route 管理（票 14）也在這裡，**精靈跑完之前也不匿名開放**（票 14a）：否則那一刻匿名的人可以
#: 把紅燈 Route 停用、再按完成。精靈第 5 步只需要刪除，它走 `DELETE /setup/routes/{id}`。
#: `/jellyfin` 只收媒體庫清單那一支：之後掛在它底下的端點照預設規則（登入即可）另外決定。
#:
#: `issues` 與 `reconcile` 從 M2 票 05 起也在這裡：修正與對帳是管理員的事（plan §6、brief §11）。
#: `files`（rematch，M2 票 08）同一個理由：改一個檔案的處置會拆掉或建起媒體庫裡的鏈接。
#: `/reconcile` 沒有子路徑，前綴比對對它就是完全比對——`_under_any` 的第一個條件。
ADMIN_PREFIXES = (
    "/settings",
    "/routes",
    "/jellyfin/libraries",
    "/issues",
    "/reconcile",
    "/review",
    "/files",
    # RSS（M3 票 08）：聚合 feed 的網址帶 token（它就是憑證），綁定會替整個家送單。
    "/rss",
    # 週報（M4 票 131）：說的是審核、Issue、RSS 這幾頁的事，那幾頁只有管理員進得去。
    "/weekly",
)

#: 只有管理員做得了的**單一方法**（M2 票 04）。`(方法, 路徑樣式)`，樣式裡的 `*` 配一段。
#:
#: 上面那一份說的是「這整塊是 admin」，這一份說的是「**這一個動詞**在這條路徑上是 admin，
#: 它的兄弟不是」。`/jobs` 整組不可以是 admin——一般使用者要送得了單、看得到自己的 job
#: （brief §11）——而刪除是 admin 的事（plan §6，2026-09-22 拍板）。兩件事在同一條路徑上，
#: 所以前綴分不開它們。
#:
#: 估算與刪除一起：對話框打開時算的那一份逐一 `stat` 每一個檔案（brief §9.2），按不到
#: 刪除的人不必替他算。
ADMIN_ROUTES: tuple[tuple[str, str], ...] = (
    ("DELETE", "/jobs/*"),
    ("GET", "/jobs/*/deletion"),
    # 重新入庫會動媒體庫（M2 票 10）；`POST /jobs` 與重試不是——`user` 送單之後要按得到重試。
    ("POST", "/jobs/*/reimport"),
    # 審核是 admin 的事（M2 票 07）；`GET /plans/*` 不是——`user` 看得到自己那筆為什麼停下來。
    ("PUT", "/plans/*/items"),
    ("POST", "/plans/*/approve"),
    ("POST", "/plans/*/reject"),
)


class Access(StrEnum):
    """一個請求要過哪一道門。規則只寫在 `access_of` 一處，門禁照它放行或擋下。"""

    #: 不必登入（`ANONYMOUS_PATHS`）。
    ANONYMOUS = "anonymous"
    #: 精靈的開場（`SETUP_OPENING_PATHS`）：擁有者成立之前匿名，之後只有管理員。
    SETUP_OPENING = "setup_opening"
    #: 精靈其餘的端點：擁有者成立之前誰都不行，之後只有管理員（`api/gate._setup_verdict`）。
    SETUP = "setup"
    #: 只有管理員（`ADMIN_PREFIXES`、`ADMIN_ROUTES`）。
    ADMIN = "admin"
    #: 登入就可以。沒被上面三種認領的路徑都落在這裡——預設拒絕的那一半是「要登入」。
    SIGNED_IN = "signed_in"


def access_of(method: str, path: str) -> Access:
    """`path` 相對於 `/api`。只看方法與路徑，不看是誰——那是 `api/gate.ApiGate._verdict` 的事。

    `tests/integration/test_auth_api.py` 的 `TestWhoEachEndpointIsFor` 拿它對 app 上的每一條路由
    逐條比對一份寫死的分類表，新增端點而沒決定它是誰的，紅的是那一支。
    """
    if path in ANONYMOUS_PATHS:
        return Access.ANONYMOUS
    if (method, path) in SETUP_OPENING_PATHS:
        return Access.SETUP_OPENING
    if _under_any(path, (SETUP_PREFIX,)):
        return Access.SETUP
    if _under_any(path, ADMIN_PREFIXES) or _is_admin_route(method, path):
        return Access.ADMIN
    return Access.SIGNED_IN


def admits(access: Access, role: Role) -> bool:
    """擁有者成立之後，一個登入的人過不過得了這一道門。門禁對登入的人照它判，命令登錄表給一個人哪些工具也照它。

    精靈（`SETUP`、`SETUP_OPENING`）在擁有者成立之後與 `ADMIN` 同一條：只有管理員（票 06i：
    跑完之後它就是設定頁的寫入端點）。
    """
    match access:
        case Access.ANONYMOUS | Access.SIGNED_IN:
            return True
        case Access.ADMIN | Access.SETUP | Access.SETUP_OPENING:
            return role is Role.ADMIN


def _under_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _is_admin_route(method: str, path: str) -> bool:
    """`ADMIN_ROUTES` 上有沒有哪一條同時配上這個方法與這條路徑。

    **逐段比，不是前綴比**：樣式裡的 `*` 配掉一段（job hash 就落在那裡），所以
    `DELETE /jobs/<hash>` 配得上而 `POST /jobs` 配不上——後者正是一般使用者要按的那一顆。
    """
    segments = path.split("/")
    return any(
        method == wanted and _segments_match(pattern.split("/"), segments)
        for wanted, pattern in ADMIN_ROUTES
    )


def _segments_match(pattern: list[str], segments: list[str]) -> bool:
    return len(pattern) == len(segments) and all(
        wanted in ("*", actual) for wanted, actual in zip(pattern, segments, strict=True)
    )
