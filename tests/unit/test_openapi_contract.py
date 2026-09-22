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
"""

from __future__ import annotations

import inspect
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from berth.api import jellyfin as jellyfin_api
from berth.api import jobs as jobs_api
from berth.api import routes as routes_api
from berth.domain import enums
from berth.main import create_app
from berth.services import jellyfin_access

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
}

#: 拒絕的形狀（`{reason, detail}` 與 Route 多的那兩格）與 SSE 的推播。前端直接取這幾個
#: （`Schemas['JobRefusalOut']`…），所以欄位增減也要讓產出檔過期。
MODELS = ("JobRefusalOut", "RouteRefusalOut", "AccessRefusalOut", "JobSignalOut")


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
