"""前端那四組形狀是**產出的**，不是手抄的（M2 票 02）。

M1 票 02 立了閘門（`pnpm gen:api` + CI 的 `git diff --exit-code -- src/api/schema.d.ts`），
但拒絕理由與 SSE 的推播沒走它：後端的封閉集合不是 pydantic model，FastAPI 產的 OpenAPI 裡
沒有它們，`openapi-typescript` 自然產不出來，於是前端各抄了一份。抄來的那幾份在後端改了
封閉集合時不會紅——畫面上會少一句話，而沒有任何東西會說。

所以這裡查兩件事：**封閉集合與拒絕的形狀進得了 OpenAPI**，以及**簽進版控的產出沒有過期**。
第二件與 CI 那一行 `git diff` 守的是同一件事，差別是它在本機 `pytest` 就紅，不必等 CI 跑完
產生器。

**拒絕理由的集合是掃出來的**（`berth.domain.enums` 裡名字以 `Refusal` 結尾的每一個），不是
在這裡列一份：M2 之後每一張票都會加拒絕理由，列一份的話第四個 enum 加進來時這裡不會紅。

第三件是 `TestDeclaringWhatEachEndpointRefuses`：**會拒絕的端點都要在 `responses=` 裡宣告**。
它走訪 `create_app()` 的每一條路由，拿那條路由**物件**上的 `responses` 與它的 handler 實際
丟得出來的拒絕比（票 02a）。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import re
import textwrap
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts

import berth.api
from berth.api import files as files_api
from berth.api import issues as issues_api
from berth.api import jellyfin as jellyfin_api
from berth.api import jobs as jobs_api
from berth.api import plans as plans_api
from berth.api import review as review_api
from berth.api import routes as routes_api
from berth.api.routes import route_refusal, route_responses
from berth.domain import RouteRefusal, enums
from berth.main import create_app
from berth.services import jellyfin_access
from berth.services.routes import RouteRejectedError

REPO_ROOT = Path(__file__).resolve().parents[2]

#: `pnpm gen:api` 的產出，簽進版控（`web/package.json` 的 `gen:api`）。
GENERATED = REPO_ROOT / "web" / "src" / "api" / "schema.d.ts"


def _refusal_enums() -> dict[str, type[StrEnum]]:
    """`domain/enums.py` 裡每一個拒絕理由的封閉集合。命名慣例就是登記簿。"""
    return {
        name: member
        for name, member in vars(enums).items()
        if inspect.isclass(member) and issubclass(member, StrEnum) and name.endswith("Refusal")
    }


REFUSALS = _refusal_enums()

#: 每一個拒絕理由 → 回它的那一張「理由 → 狀態碼」表。`test_every_refusal_enum_is_listed_here`
#: 守著這份對照本身：新加一個 enum 而沒有人給它狀態碼時，紅的是那一條。
STATUS_TABLES: dict[str, dict[Any, int]] = {
    "JobRefusal": jobs_api._STATUS,
    "RouteRefusal": routes_api._STATUS,
    "AccessRefusal": jellyfin_api._STATUS,
    "IssueRefusal": issues_api._STATUS,
    "ReviewRefusal": review_api._STATUS,
    "PlanRefusal": plans_api._STATUS,
    "RematchRefusal": files_api._STATUS,
}

#: 拒絕的形狀（`{reason, detail}` 與 Route 多的那兩格）與 SSE 的推播。前端直接取這幾個
#: （`Schemas['JobRefusalOut']`…），所以欄位增減也要讓產出檔過期。
MODELS = (
    "JobRefusalOut",
    "RouteRefusalOut",
    "AccessRefusalOut",
    "IssueRefusalOut",
    "ReviewRefusalOut",
    "PlanRefusalOut",
    "RematchRefusalOut",
    "JobSignalOut",
)


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    """OpenAPI 文件本人。不跑 lifespan、不連任何東西（同 `berth openapi`）。"""
    return create_app().openapi()


def union_members(text: str, name: str) -> set[str]:
    """`schema.d.ts` 裡 `Name: "a" | "b";` 那一行列出的成員。

    **只讀那一行**：這條規則要守的是封閉集合本身，所以檔案其餘部分改名、重排或重新格式化
    都不該讓它讀出不同的東西（`TestReadingTheGeneratedTypes` 兩個方向各驗一次）。開頭要求是
    引號，`reason: components["schemas"]["JobRefusal"];` 這種引用它的行才不會被當成宣告。
    """
    match = re.search(rf'^\s*{re.escape(name)}: ("[^;]+);$', text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"{name} is not declared in {GENERATED.name}")
    return set(re.findall(r'"([^"]*)"', match.group(1)))


def object_fields(text: str, name: str) -> set[str]:
    """`schema.d.ts` 裡 `Name: { ... };` 那一塊的欄位名。

    聯集那一支讀的是成員，這一支讀的是形狀——沒有它，「後端把 `hash` 改名卻沒重跑產生器」
    這件事在 `pytest` 這一關是靜的（只剩 CI 的 `git diff` 抓得到）。靠縮排找結尾而不是數
    大括號：產出的那一份縮排是穩定的，而巢狀的物件欄位本來就不該被當成這一層的欄位。
    """
    lines = text.splitlines()
    opener = re.compile(rf"^(\s*){re.escape(name)}: \{{$")
    for index, line in enumerate(lines):
        start = opener.match(line)
        if start is None:
            continue
        indent = start.group(1)
        field = re.compile(rf"^{indent}    ([A-Za-z_][A-Za-z0-9_]*)\??:")
        fields: set[str] = set()
        for row in lines[index + 1 :]:
            if row == f"{indent}}};":
                return fields
            found = field.match(row)
            if found is not None:
                fields.add(found.group(1))
        raise AssertionError(f"{name} in {GENERATED.name} never closes")
    raise AssertionError(f"{name} is not declared in {GENERATED.name}")


class TestRefusalReasons:
    """拒絕理由的封閉集合（`{reason, detail}` 的那一格）。"""

    def test_every_refusal_enum_is_listed_here(self) -> None:
        """M2 的每一張票都會加拒絕理由。新加一個 enum 就要在 `STATUS_TABLES` 給它一張表，
        否則它進不了任何一支端點的文件，而下面每一條都只會跑既有的那幾個。"""
        assert set(REFUSALS) == set(STATUS_TABLES)

    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_the_document_carries_every_member(self, document: dict[str, Any], name: str) -> None:
        schema = document["components"]["schemas"][name]

        assert schema["enum"] == [member.value for member in REFUSALS[name]]

    @pytest.mark.parametrize("name", sorted(REFUSALS))
    def test_the_generated_types_are_not_stale(self, name: str) -> None:
        """後端加了一種理由卻沒重跑 `pnpm gen:api` 時，紅的就是這一條。"""
        members = union_members(GENERATED.read_text(encoding="utf-8"), name)

        assert members == {member.value for member in REFUSALS[name]}


class TestRefusalShapes:
    """拒絕與 SSE 推播的**形狀**。理由的集合對了、欄位改了名一樣會讓前端讀到 `undefined`。"""

    @pytest.mark.parametrize("name", MODELS)
    def test_the_document_carries_the_model(self, document: dict[str, Any], name: str) -> None:
        assert name in document["components"]["schemas"]

    @pytest.mark.parametrize("name", MODELS)
    def test_the_generated_types_are_not_stale(self, document: dict[str, Any], name: str) -> None:
        expected = set(document["components"]["schemas"][name]["properties"])

        assert object_fields(GENERATED.read_text(encoding="utf-8"), name) == expected

    def test_the_state_the_stream_pushes_is_the_job_state_enum(
        self, document: dict[str, Any]
    ) -> None:
        """推的是 `JobState` 而不是自由字串——前端拿它比對狀態，打錯就該在 `tsc` 紅。"""
        state = document["components"]["schemas"]["JobSignalOut"]["properties"]["state"]

        assert state["$ref"] == "#/components/schemas/JobState"

    def test_the_route_refusal_carries_the_two_counts(self, document: dict[str, Any]) -> None:
        """`route_in_use` 才有的兩格（票 14a）：畫面照它說「N 筆下載、M 個入庫檔案」，
        不該去解析 `detail`。它們是選填——其餘理由根本不送。"""
        schema = document["components"]["schemas"]["RouteRefusalOut"]

        assert set(schema["properties"]) == {"reason", "detail", "jobs", "ledger_entries"}
        assert set(schema["required"]) == {"reason", "detail"}


class TestStatusTables:
    """「理由 → 狀態碼」的表要涵蓋整個封閉集合。

    三支 `*_refusal` 都直接以 `[]` 取值，所以漏一種就是執行期的 `KeyError`。以前是
    `.get(reason, 422)`：漏掉的那一種會靜靜變成 422，也就是把一種沒人想過的拒絕說成
    「你送錯東西了」。表同時餵 OpenAPI 的 `responses`，所以漏的那一種在文件上也不存在。
    """

    @pytest.mark.parametrize("name", sorted(STATUS_TABLES))
    def test_every_reason_has_a_status_code(self, name: str) -> None:
        assert set(STATUS_TABLES[name]) == set(REFUSALS[name])

    def test_every_access_error_maps_to_a_reason(self) -> None:
        """`access_refusal` 以 `type(refusal)` 精確查表，所以 `services/jellyfin_access.py`
        每多一個例外類別就要在這裡登記一次，否則它到了 api 這一層是 `KeyError`。"""
        raised = {
            member
            for member in vars(jellyfin_access).values()
            # `__module__` 而不是只看名字：那個模組也 import 了別處的例外，它們不歸這張表管。
            if inspect.isclass(member)
            and issubclass(member, Exception)
            and member.__module__ == jellyfin_access.__name__
        }

        assert raised == set(jellyfin_api._REFUSALS)


class TestReadingTheGeneratedTypes:
    """`union_members` 與 `object_fields` 自己的雙向變異：拿掉一個成員或欄位要讀出不同的
    東西，改別的地方不能。沒有這一段，上面那些斷言可能只是在讀一個永遠相等的東西。"""

    UNION = '        JobRefusal: "route_missing" | "job_missing";\n'
    OBJECT = (
        "        JobSignalOut: {\n"
        "            /** Hash */\n"
        "            hash: string;\n"
        '            state: components["schemas"]["JobState"];\n'
        "            /** Progress */\n"
        "            progress: number;\n"
        "        };\n"
    )
    NOISE = (
        '        SomethingElse: "route_missing" | "renamed";\n'
        '            reason: components["schemas"]["JobRefusal"];\n'
        "    /** JobRefusal */\n"
    )

    def test_it_reads_the_members_of_that_one_union(self) -> None:
        assert union_members(self.UNION, "JobRefusal") == {"route_missing", "job_missing"}

    def test_dropping_a_member_changes_what_it_reads(self) -> None:
        mutated = self.UNION.replace(' | "job_missing"', "")

        assert union_members(mutated, "JobRefusal") == {"route_missing"}

    def test_it_reads_the_fields_of_that_one_object(self) -> None:
        assert object_fields(self.OBJECT, "JobSignalOut") == {"hash", "state", "progress"}

    def test_renaming_a_field_changes_what_it_reads(self) -> None:
        mutated = self.OBJECT.replace("hash: string;", "info_hash: string;")

        assert object_fields(mutated, "JobSignalOut") == {"info_hash", "state", "progress"}

    def test_an_optional_field_is_still_a_field(self) -> None:
        """`jobs?: number | null` 那兩格（`RouteRefusalOut`）。"""
        optional = self.OBJECT.replace("progress: number;", "progress?: number | null;")

        assert "progress" in object_fields(optional, "JobSignalOut")

    def test_renaming_and_reformatting_the_rest_does_not(self) -> None:
        assert union_members(self.NOISE + self.UNION, "JobRefusal") == union_members(
            self.UNION, "JobRefusal"
        )
        assert object_fields(self.NOISE + self.OBJECT, "JobSignalOut") == object_fields(
            self.OBJECT, "JobSignalOut"
        )

    def test_what_is_not_there_is_an_error_not_an_empty_answer(self) -> None:
        """產生器換了輸出形狀時要說話，而不是靜靜地讀出「沒有成員」然後通過。"""
        with pytest.raises(AssertionError):
            union_members(self.UNION, "RouteRefusal")
        with pytest.raises(AssertionError):
            object_fields(self.OBJECT, "RouteRefusalOut")


# --- 會拒絕就要宣告（票 02a）-------------------------------------------------


def _api_modules() -> list[ModuleType]:
    """`berth.api` 底下的每一個模組。"""
    return [
        importlib.import_module(f"{berth.api.__name__}.{info.name}")
        for info in pkgutil.iter_modules(berth.api.__path__)
    ]


def _called_name(func: ast.expr) -> str | None:
    """被呼叫的那一個名字。`routes_api.route_refusal(...)` 取 `route_refusal`。

    帶模組前綴的寫法也要認得：只認裸名字的話，換一種 import 風格就能靜悄悄地繞過整條規則
    （`TestReadingWhatAHandlerRaises` 兩種寫法各驗一次）。
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _builds_refusal(node: ast.AST) -> str | None:
    """這個節點是不是在**組**一份拒絕的 body（`RouteRefusalOut(...)`）。

    要求是 `Call`，不是光提到那個名字：`access_responses()` 把 `AccessRefusalOut` 當參數傳
    給 `refusal_responses`，它整理的是文件，不是在拒絕誰。組了就算數，不要求同一句 `raise`
    ——三支 helper 都是先組 body 再 `return HTTPException(...)`，而它們正是被跟進來讀的。
    """
    if not isinstance(node, ast.Call):
        return None
    name = _called_name(node.func)
    return name if name is not None and name.endswith("RefusalOut") else None


def _raised_helper(node: ast.AST) -> str | None:
    """`raise route_refusal(...)` 那一句被丟出來的東西是哪一支函式組的。"""
    if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
        return _called_name(node.exc.func)
    return None


def refusal_helpers() -> dict[str, str]:
    """api 底下每一支「把拒絕翻成 `HTTPException`」的函式 → 它組出來的那個 model。

    **掃出來而不是在這裡列一份**：第四組拒絕（M2 之後每張票都可能加）自帶的 helper 不必記得
    回來登記。認法就是「它組 `*RefusalOut`」——那是拒絕的形狀本身，而三支現有的
    （`route_refusal`、`access_refusal`、`jobs._refuse`）都只為了這件事存在。
    """
    found: dict[str, str] = {}
    for module in _api_modules():
        for name, member in vars(module).items():
            if not inspect.isfunction(member) or member.__module__ != module.__name__:
                continue
            for node in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(member)))):
                model = _builds_refusal(node)
                if model is None:
                    continue
                # 同名而組不同 model 的兩支 helper 會讓下面的名字查表說謊。
                assert found.get(name, model) == model, f"{name} builds two shapes"
                found[name] = model
    return found


HELPERS = refusal_helpers()

#: 拒絕的形狀。`responses=` 裡其它的 model（將來某支端點的 404 回別的東西）不歸這條規則管。
REFUSAL_MODELS = frozenset(HELPERS.values())


def raised_models(endpoint: Callable[..., Any]) -> set[str]:
    """這支 handler 實際丟得出哪幾種拒絕的形狀。

    兩條認法：`raise <helper>(...)`（跨模組也算——精靈的兩支借 `api/routes.py` 的
    `route_refusal`），以及在自己身上直接組一份 `*RefusalOut`。跟著同模組的函式呼叫往下走，
    因為 `mark_played` / `mark_unplayed` 把 `try` 交給共用的 `_mark`，只看 handler 自己的
    body 會讀成「它不會拒絕」。

    看的是語法樹而不是數字串：`PLAYED_RESPONSES` 那種先存成常數再用的寫法（票 02 因此收手）
    在這裡根本不經過——`responses` 從路由物件上讀，是執行期的值。

    **跟不進別的 api 模組**（`route_refusal` 那三支 helper 靠名字認得，其餘不行）：哪一天有支
    handler 把 `try` 交給另一個模組的共用函式，這裡會讀成「它不會拒絕」而要求拿掉正確的宣告。
    那是**假紅**，不是靜靜放過——會有人看到並回來補這一段。
    """
    seen: set[str] = set()
    models: set[str] = set()

    def walk(target: Callable[..., Any]) -> None:
        module = inspect.getmodule(target)
        definition = ast.parse(textwrap.dedent(inspect.getsource(target))).body[0]
        assert isinstance(definition, ast.FunctionDef | ast.AsyncFunctionDef)
        # 只看 body：decorator 上的 `responses=access_responses(...)` 是宣告，不是拒絕。
        for statement in definition.body:
            for node in ast.walk(statement):
                model = _builds_refusal(node)
                if model is not None:
                    models.add(model)
                raised = _raised_helper(node)
                if raised in HELPERS:
                    models.add(HELPERS[raised])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    nested = getattr(module, node.func.id, None)
                    if (
                        inspect.isfunction(nested)
                        and module is not None
                        and nested.__module__ == module.__name__
                        and nested.__qualname__ not in seen
                    ):
                        seen.add(nested.__qualname__)
                        walk(nested)

    walk(endpoint)
    return models


def declared_models(route: APIRoute) -> set[str]:
    """這條路由的 OpenAPI `responses` 上宣告了哪幾種拒絕的形狀。

    只算 4xx / 5xx 那幾格：拒絕的形狀掛在 200 上不算宣告了拒絕，那是在說成功也長這樣。
    看開頭那個數字而不是 `int()`，因為 OpenAPI 的 key 也可以是 `"4XX"` 這種範圍。
    """
    return {
        response["model"].__name__
        for code, response in route.responses.items()
        if str(code).startswith(("4", "5"))
        and "model" in response
        and response["model"].__name__ in REFUSAL_MODELS
    }


class Endpoint(NamedTuple):
    """一條 API 路由，連它掛進 app 之後的完整路徑。"""

    path: str
    methods: frozenset[str]
    route: APIRoute


def api_endpoints(app: FastAPI) -> list[Endpoint]:
    """這個 app 上的每一條 API 路由。

    走 `iter_route_contexts`（FastAPI 自己產 OpenAPI 時攤平路由用的那一支）而不是讀
    `app.routes`：`include_router` 的結果從 0.141 起包在 `_IncludedRouter` 裡，直接讀
    `app.routes` 一條 `APIRoute` 都拿不到——而**空的 `parametrize` 是會通過的**（票 02a
    第一版就是這樣「綠燈」的）。`test_it_walks_every_operation_in_the_document` 釘著這件事。
    """
    found: list[Endpoint] = []
    for context in iter_route_contexts(app.routes):
        route = context.route
        if not isinstance(route, APIRoute):
            continue
        # `APIRoute` 一定有路徑與方法；`RouteContext` 的型別替 Mount 那種留了 `None`。
        assert context.path is not None
        found.append(Endpoint(context.path, frozenset(context.methods or ()), route))
    return found


ENDPOINTS = api_endpoints(create_app())


class TestDeclaringWhatEachEndpointRefuses:
    """**會拒絕就要宣告**。票 02 試過數原始碼裡 `raise x_refusal(` 與 `responses=` 各出現
    幾次，`PLAYED_RESPONSES` 這種先存成常數再用的寫法數不到，放寬到數得到就等於沒在守東西，
    所以拿掉了（票 02 Comments）。這裡改成拿**路由物件上的 `responses`**（執行期的值，怎麼寫
    都一樣）比 handler 的**語法樹**，兩邊都不是字串比對。

    兩個方向一起要求：漏宣告的話前端在 OpenAPI 上看不到那個封閉集合（票 02 要解的就是這個），
    過度宣告的話文件說得出端點根本丟不出來的形狀——`refusal_responses` 的 docstring
    寫明「收的是端點真的會回的那幾種」。
    """

    def test_the_helpers_are_the_ones_we_know(self) -> None:
        """掃出來的登記簿本身：多一支少一支都要有人看到。

        **名字要在整個 `berth.api` 底下唯一**（`refusal_helpers` 的那一句 assert 守著）：
        登記簿以名字為鍵，所以第二支 `_refuse` 會讓查表說謊——`api/issues.py` 那一支因此
        叫 `issue_refusal`，與 `route_refusal`、`access_refusal` 同一個命名。
        """
        assert HELPERS == {
            "route_refusal": "RouteRefusalOut",
            "access_refusal": "AccessRefusalOut",
            "issue_refusal": "IssueRefusalOut",
            "review_refusal": "ReviewRefusalOut",
            "plan_refusal": "PlanRefusalOut",
            "rematch_refusal": "RematchRefusalOut",
            "_refuse": "JobRefusalOut",
        }

    def test_it_walks_every_operation_in_the_document(self, document: dict[str, Any]) -> None:
        """走訪到的要**剛好**是文件上的每一個 operation。

        沒有這一條，下面那條逐路由的規則在清單塌成空的時候仍然是綠的（`parametrize` 收到
        空 list 就產生一個什麼都不驗的項目）——閘門看起來還在，其實已經沒有在守東西了。
        """
        operations = {
            (path, method.upper())
            for path, methods in document["paths"].items()
            for method in methods
        }

        walked = {(endpoint.path, method) for endpoint in ENDPOINTS for method in endpoint.methods}

        assert walked == operations

    @pytest.mark.parametrize(
        "endpoint", ENDPOINTS, ids=lambda row: f"{sorted(row.methods)[0]} {row.path}"
    )
    def test_it_declares_exactly_what_it_raises(self, endpoint: Endpoint) -> None:
        assert declared_models(endpoint.route) == raised_models(endpoint.route.endpoint)


# --- 給下面那組變異用的假 handler。沒有一支會被呼叫到，讀的是它們的語法樹 ---


def _work() -> None:
    """假的 services 命令。"""
    raise RouteRejectedError(RouteRefusal.ROUTE_MISSING, "")


def _refuses_plainly() -> None:
    """一支會拒絕的 handler。"""
    try:
        _work()
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal


def _refuses_after_renaming() -> None:
    """與上面同一支，只是換了區域變數的名字、改寫了 docstring、拆了行。

    讀出來要**一樣**：這條規則守的是「它丟不丟得出拒絕」，不是原始碼長什麼樣子。
    """
    try:
        _work()
    except RouteRejectedError as rejected_by_services:
        raise route_refusal(
            rejected_by_services,
        ) from rejected_by_services


def _refuses_through_the_module() -> None:
    """同一件事，改用帶模組前綴的寫法。只認裸名字的話這一支就靜悄悄地不必宣告了。"""
    try:
        _work()
    except RouteRejectedError as refusal:
        raise routes_api.route_refusal(refusal) from refusal


def _delegates_the_refusal() -> None:
    """`mark_played` / `mark_unplayed` 的形狀：`try` 在共用的那一支裡。"""
    _refuses_plainly()


def _refuses_and_recurses(depth: int) -> None:
    """會叫到自己的 handler。`seen` 沒有先放入入口函式的話，這裡是無窮遞迴。"""
    if depth > 0:
        _refuses_and_recurses(depth - 1)
    raise route_refusal(RouteRejectedError(RouteRefusal.ROUTE_MISSING, ""))


def _never_refuses() -> None:
    _work()


class TestReadingWhatAHandlerRaises:
    """`raised_models` 與 `declared_models` 自己的雙向變異（全域 CLAUDE.md）。

    沒有這一段，上面那條逐路由的規則可能只是在比兩個永遠相等的空集合——而它守的又剛好是
    「不要留一條靠運氣被遵守的規則」。
    """

    def test_it_reads_the_refusal_a_handler_raises(self) -> None:
        assert raised_models(_refuses_plainly) == {"RouteRefusalOut"}

    def test_it_follows_a_handler_that_delegates(self) -> None:
        """只看 handler 自己的 body 會把 `mark_played` 讀成「它不會拒絕」，於是那兩支真正的
        `PLAYED_RESPONSES` 反而被判成過度宣告。"""
        assert raised_models(_delegates_the_refusal) == {"RouteRefusalOut"}

    def test_it_reads_a_refusal_raised_through_its_module(self) -> None:
        """`routes_api.route_refusal(...)`。換一種 import 風格不該讓這條規則消失。"""
        assert raised_models(_refuses_through_the_module) == {"RouteRefusalOut"}

    def test_a_handler_that_calls_itself_terminates(self) -> None:
        """自我遞迴的 handler 不該把走訪帶進無窮迴圈。

        停得下來靠的是呼叫點那一份 `seen`（跟進去之前先記下來），不是入口函式的名字——
        所以這一條是回歸護欄，不是雙向變異的那一對（拿掉 `seen` 才會紅）。
        """
        assert raised_models(_refuses_and_recurses) == {"RouteRefusalOut"}

    def test_a_handler_that_does_not_refuse_reads_empty(self) -> None:
        assert raised_models(_never_refuses) == set()

    def test_a_refusal_shape_on_a_success_code_is_not_a_declaration(self) -> None:
        """`{200: {"model": RouteRefusalOut}}` 說的是成功也長這樣，不是宣告了拒絕。"""
        app = FastAPI()
        app.post("/ok", responses={200: {"model": routes_api.RouteRefusalOut}})(_never_refuses)

        (endpoint,) = api_endpoints(app)

        assert declared_models(endpoint.route) == set()

    def test_renaming_and_reformatting_does_not_change_what_it_reads(self) -> None:
        assert raised_models(_refuses_after_renaming) == raised_models(_refuses_plainly)

    def test_dropping_the_declaration_turns_that_endpoint_red(self) -> None:
        """**票 02a 的驗收本身**：把 `responses=` 拿掉就紅。兩支掛的是同一個 handler，
        差別只有宣告。"""
        app = FastAPI()
        app.post("/declared", responses=route_responses(RouteRefusal.ROUTE_MISSING))(
            _refuses_plainly
        )
        app.post("/bare")(_refuses_plainly)

        agrees = {
            endpoint.path: declared_models(endpoint.route) == raised_models(endpoint.route.endpoint)
            for endpoint in api_endpoints(app)
        }

        assert agrees == {"/declared": True, "/bare": False}

    def test_declaring_what_it_cannot_raise_turns_it_red(self) -> None:
        """反方向：文件說得出端點根本丟不出來的形狀，一樣紅。"""
        app = FastAPI()
        app.post("/overdeclared", responses=route_responses(RouteRefusal.ROUTE_MISSING))(
            _never_refuses
        )

        (endpoint,) = api_endpoints(app)

        assert declared_models(endpoint.route) != raised_models(endpoint.route.endpoint)
