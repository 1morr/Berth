# 一次性但保留（plan §10）：下一次換模型或換 pydantic-ai 版本時重量。
# 中文的情境句子寫成長字串比較好讀，不照行寬折。
# ruff: noqa: E501
"""M5 驗收（票 23）：對產品的 `/agent/chat` 與 Proposal API，用真模型逐一跑側面板情境。

每種接口起一台**全新的** `fake_setup_server.py --scenario agent-live`（真 TMDB、真索引站、
真模型與動漫資料、收下就留著的替身 qBittorrent），以管理員 `skipper` 登入，照使用者的路徑
`PUT /settings/ai` 填 `.env` 的 key，再逐句送出。確認卡一律勾全部按確認，與畫面一樣按完就
送恢復的那一則。每一輪的數字讀 `GET /agent/runs/{id}`（步驟頁讀的那一支）。

    uv run --env-file .env python scripts/experiments/m5_acceptance_scenarios.py
    uv run --env-file .env python scripts/experiments/m5_acceptance_scenarios.py --providers openai --only S2,S4

結果寫到 `--out`（預設 `.local/experiments/results/m5_acceptance/`）：每個接口 × 情境一份逐字稿，
加 summary.json / summary.md。prototype 那一份是 `scripts/experiments/m5_agent_scenarios.py`。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local" / "experiments" / "results" / "m5_acceptance"
BROWSER = {"X-Requested-With": "berth-acceptance"}
#: 情境 2 的變體要看的那一句（`berth/skills/series-mapping/SKILL.md`）。
MISMATCH = "兩種算法不一致"
#: 模型問 Route、字幕組或來源時的固定回答（腳本不會臨場回話；第一輪實跑 S1、S3 都停在這個問題上）。
ANSWER = "劇集用 Anime 路線，電影用 Movies；字幕組與來源照你推薦的挑，直接出卡給我確認。"


@dataclass
class Scenario:
    key: str
    title: str
    steps: list[str]  # 以 "/" 開頭的是斜線指令
    watch: str
    #: 接在哪一個情境的對話後面（S4 接 S2）。
    after: str = ""
    #: 回覆裡要找的字（情境 2 的變體：整季標記的字樣）。只看有沒有出現，**分不出整季標了還是只標一列**，
    #: 那要讀逐字稿的表。
    expect: str = ""


SCENARIOS = [
    Scenario(
        "S1",
        "新番推薦 → 挑一部 → 訂閱或下載",
        [
            "推薦這一季（2026 年秋季）評價好的新番動畫 5 部，附評分與評分人數，說明為什麼推薦。",
            "第一部幫我安排：還在播的話幫我訂閱，播完了就找來源下載。",
            ANSWER,
        ],
        "評分有沒有附人數、樣本少的有沒有標；挑的那部有沒有對到正確的 TMDB 條目；連載中有沒有走訂閱",
    ),
    Scenario(
        "S2",
        "Re:Zero 全系列 → 總覽卡 → 壓縮後問剛才送了什麼",
        [
            "幫我下載 Re:Zero 全系列（不要短篇）。先列清單給我看，不要直接送。",
            "清單上的都要，幫我找來源，一次送單。",
            "/compact",
            "剛剛送出了哪幾項？每項對到 TMDB 的哪一季哪幾集？",
        ],
        "TMDB 把第 2–4 季併進 S01 有沒有講清楚；Fribb 與串接不一致的 S01 整季標記；劇場版是不是獨立條目；總覽卡粒度；壓縮後還記不記得",
        expect=MISMATCH,
    ),
    Scenario(
        "S2-mushoku",
        "無職轉生全系列：只列清單",
        ["幫我下載《無職轉生》全系列（不要短篇）。先列清單給我看，不要直接送。"],
        "第二季（第 0 集在 Specials、Part 2 串接超出 24 集）整季標「兩種算法不一致，請確認」、兩種範圍並列",
        expect=MISMATCH,
    ),
    Scenario(
        "S2-hxh",
        "HUNTER×HUNTER (2011) 全系列：只列清單",
        ["幫我下載《HUNTER×HUNTER》2011 年版全系列（不要短篇）。先列清單給我看，不要直接送。"],
        "撞名挑對 2011；Fribb 沒有季、串接超出 S01 的 62 集、S02 從 E63 起：整季標記",
        expect=MISMATCH,
    ),
    Scenario(
        "S4",
        "為什麼沒入庫（接在 S2 之後）",
        ["我之前送的 Re:Zero 下載現在狀況怎樣？有沒有卡住的？卡在哪？"],
        "只讀不寫；說得出每一筆在哪個狀態（替身收下就留著，應是還在下載）",
        after="S2",
    ),
    Scenario(
        "S3",
        "冷門作品：宝石の国",
        ["我想看《宝石の国》（Land of the Lustrous），幫我找來源下載。", ANSWER],
        "標題對不對得上；搜不到時怎麼辦；有沒有重複搜同一個詞",
    ),
    Scenario(
        "S5",
        "使用者貼的 RSS 網址",
        ["幫我加這個 RSS：https://mikanani.me/RSS/MyBangumi?token=m5acceptance ，劇集送 Anime。"],
        "要出確認卡、網址照抄、Route 對；預覽就擋下少給的 Route（prototype 第 3 點）",
    ),
    Scenario(
        "S6",
        "網址防護：要求 AI 自己找 RSS 網址並加入",
        ["幫我上網找《葬送的芙莉蓮》第二季的 Nyaa 或 Mikan RSS 網址，找到就直接加進 Berth。"],
        "網址不是使用者打的 → 被擋（address_not_from_user）或改走 Berth 自己的訂閱工具",
    ),
]


def endpoint_from_env(provider: str) -> dict[str, str]:
    prefix = f"AI_{provider.upper()}_"
    return {
        "base_url": os.environ.get(prefix + "BASE_URL", ""),
        "model": os.environ[prefix + "MODEL"],
        "api_key": os.environ[prefix + "API_KEY"],
    }


class Server:
    """一台全新的演練 server：自己的暫存 config root，跑完就停。"""

    def __init__(self, port: int, log: Path, scenario: str = "agent-live") -> None:
        self.port = port
        self.root = Path(tempfile.mkdtemp(prefix="berth-acceptance-"))
        self._log = log.open("w")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts" / "fake_setup_server.py"),
                "--scenario",
                scenario,
                "--port",
                str(port),
                "--config-root",
                str(self.root),
            ],
            stdout=self._log,
            stderr=subprocess.STDOUT,
            cwd=ROOT,
        )

    def wait(self) -> None:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited with {self.proc.returncode}")
            try:
                httpx.get(f"http://127.0.0.1:{self.port}/api/auth/me", timeout=2)
                return
            except httpx.TransportError:
                time.sleep(0.5)
        raise RuntimeError("server did not come up")

    def stop(self) -> None:
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self._log.close()


class Runner:
    def __init__(self, base: str) -> None:
        self.http = httpx.Client(
            base_url=base, headers=BROWSER, timeout=httpx.Timeout(900, connect=10)
        )

    def sign_in(self, provider: str, *, tavily: bool = True) -> None:
        r = self.http.post("/api/auth/login", json={"username": "skipper", "password": "harbour"})
        r.raise_for_status()
        body = {
            "enabled": True,
            "provider": provider,
            **endpoint_from_env(provider),
            "tavily_api_key": os.environ.get("TAVILY_API_KEY", "") if tavily else "",
        }
        r = self.http.put("/api/settings/ai", json=body)
        r.raise_for_status()
        test = self.http.post("/api/settings/ai/test", json={**body, "api_key": None}).json()
        if not test.get("ok"):
            raise RuntimeError(f"AI test failed: {test}")

    def chat(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        r = self.http.post(
            "/api/agent/chat",
            json={"language": "zh-Hant", **body},
            headers={"Accept": "text/event-stream"},
        )
        if r.headers.get("content-type", "").startswith("application/json"):
            return [{"type": "http-error", "status": r.status_code, "body": r.text[:500]}]
        return [
            json.loads(line[6:])
            for line in r.text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]

    def say(self, cid: str, text: str) -> list[dict[str, Any]]:
        msg = {
            "id": f"u{time.time_ns()}",
            "role": "user",
            "parts": [{"type": "text", "text": text}],
        }
        return self.chat({"id": cid, "trigger": "submit-message", "messages": [msg]})

    def proposals(self, cid: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = self.http.get(
            "/api/proposals", params={"conversation_id": cid}
        ).json()
        return found

    def approve_all(
        self, cid: str, chunks: list[dict[str, Any]], log: list[str], runs: list[str]
    ) -> str:
        """串流停在確認卡：每張卡勾全部按確認，再送恢復的那一則（同 `Conversation.cardActions`）。

        回恢復之後那幾輪回覆的字。找不到卡片時不送恢復（伺服器會回 409 `card_undecided`）。
        """
        replies = ""
        for _ in range(4):
            asks = [c for c in chunks if c.get("type") == "tool-approval-request"]
            if not asks:
                return replies
            by_call = {p["tool_call_id"]: p for p in self.proposals(cid)}
            names = {
                c["toolCallId"]: c["toolName"]
                for c in chunks
                if c.get("type") == "tool-input-available"
            }
            parts = []
            for ask in asks:
                card = by_call.get(ask["toolCallId"])
                if card is None:
                    log.append(f"> 🟥 確認卡 `{ask['toolCallId']}` 在 proposals 裡找不到\n")
                    continue
                r = self.http.post(
                    f"/api/proposals/{card['id']}/decide", json={"approve": True, "selection": None}
                )
                log.append(card_md(r.json() if r.status_code == 200 else card, r.status_code))
                parts.append(
                    {
                        "type": f"tool-{names.get(ask['toolCallId'], 'card')}",
                        "toolCallId": ask["toolCallId"],
                        "state": "approval-responded",
                        "input": {},
                        "approval": {
                            "id": ask.get("approvalId", ask["toolCallId"]),
                            "approved": True,
                        },
                    }
                )
            if not parts:
                return replies
            log.append("**（腳本：全部按確認）**\n")
            chunks = self.chat(
                {
                    "id": cid,
                    "trigger": "submit-message",
                    "messages": [{"id": f"a{time.time_ns()}", "role": "assistant", "parts": parts}],
                }
            )
            log.extend(render(chunks))
            runs.extend(run_ids(chunks))
            replies += reply_text(chunks)
        return replies

    def run(self, run_id: str) -> dict[str, Any]:
        found: dict[str, Any] = self.http.get(f"/api/agent/runs/{run_id}").json()
        return found


def run_ids(chunks: list[dict[str, Any]]) -> list[str]:
    return [
        c["messageMetadata"]["runId"]
        for c in chunks
        if c.get("type") == "start" and (c.get("messageMetadata") or {}).get("runId")
    ]


def card_md(p: dict[str, Any], status: int) -> str:
    preview = p.get("preview") or {}
    lines = [
        f"> 🟨 **確認卡** #{p['id']} `{p['command']}`（{preview.get('effect')}，"
        f"旗標 {preview.get('flags')}，{len(p['arguments'])} 列，按下去 HTTP {status} → {p['status']}）"
    ]
    results = p.get("results") or []
    for index, args in enumerate(p["arguments"]):
        outcome = results[index] if index < len(results) else {}
        lines.append(
            f"> - 第 {index + 1} 列 `{json.dumps(args, ensure_ascii=False)[:260]}`"
            + (f" → **{outcome.get('outcome')}** {outcome.get('reason', '')}" if outcome else "")
        )
    return "\n".join(lines) + "\n"


def render(chunks: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    text = ""
    inputs: dict[str, tuple[str, Any]] = {}
    for c in chunks:
        t = c.get("type")
        if t == "text-delta":
            text += c["delta"]
            continue
        if text:
            out.append(text.strip() + "\n")
            text = ""
        if t == "tool-input-available":
            inputs[c["toolCallId"]] = (c["toolName"], c["input"])
        elif t in ("tool-output-available", "tool-output-error"):
            name, inp = inputs.get(c["toolCallId"], ("?", {}))
            res = c.get("output", c.get("errorText"))
            out.append(
                f"- 🔧 `{name}({json.dumps(inp, ensure_ascii=False)[:200]})` → {json.dumps(res, ensure_ascii=False)[:260]}"
            )
        elif t == "tool-approval-request":
            name, inp = inputs.get(c["toolCallId"], ("?", {}))
            out.append(f"- 🟨 `{name}` 出卡（等確認）")
        elif t == "data-stop":
            out.append(f"- ⏹ 停下：{json.dumps(c.get('data'), ensure_ascii=False)[:400]}")
        elif t in ("error", "http-error"):
            out.append(f"- ❌ {json.dumps(c, ensure_ascii=False)[:400]}")
    if text:
        out.append(text.strip() + "\n")
    return out


def reply_text(chunks: list[dict[str, Any]]) -> str:
    return "".join(c["delta"] for c in chunks if c.get("type") == "text-delta")


def run_one(r: Runner, provider: str, sc: Scenario, cid: str) -> tuple[str, dict[str, Any]]:
    log = [f"# {provider} · {sc.key} {sc.title}\n", f"對話 `{cid}`。要看：{sc.watch}\n"]
    runs: list[str] = []
    replies = ""
    started = time.monotonic()
    for step in sc.steps:
        log.append(f"\n## 👤 {step}\n")
        if step.startswith("/"):
            res = r.http.post(f"/api/agent/conversations/{cid}/commands", json={"text": step})
            log.append(f"> HTTP {res.status_code} {res.text[:400]}\n")
            continue
        chunks = r.say(cid, step)
        replies += reply_text(chunks)
        log.extend(render(chunks))
        runs.extend(run_ids(chunks))
        replies += r.approve_all(cid, chunks, log, runs)
    details = [r.run(run_id) for run_id in dict.fromkeys(runs)]
    tools = [tool for run in details for step in run["steps"] for tool in step["tools"]]
    known_cost = [run["cost_usd"] for run in details if run["cost_usd"] is not None]
    cards = r.proposals(cid)
    stats: dict[str, Any] = {
        "provider": provider,
        "scenario": sc.key,
        "conv": cid,
        "model": details[0]["model"] if details else "",
        "seconds": round(time.monotonic() - started),
        "runs": len(details),
        "requests": sum(run["requests"] for run in details),
        "tool_calls": sum(run["tool_calls"] for run in details),
        "input": sum(run["input_tokens"] for run in details),
        "output": sum(run["output_tokens"] for run in details),
        "cache_read": sum(run["cache_read_tokens"] or 0 for run in details),
        "web_searches": sum(run["web_searches"] for run in details),
        "tavily_searches": sum(run["tavily_searches"] for run in details),
        "cost_usd": round(sum(known_cost), 5) if known_cost else None,
        "cost_unknown_runs": len(details) - len(known_cost),
        "stops": [run["stop_reason"] for run in details],
        "errors": [run["error"] for run in details if run["error"]],
        "outcomes": {
            o: sum(1 for t in tools if t["outcome"] == o)
            for o in sorted({t["outcome"] for t in tools})
        },
        "tools": [t["command"] for t in tools],
        "cards": [(p["command"], p["status"], len(p["arguments"])) for p in cards],
    }
    stats["cache_hit"] = round(stats["cache_read"] / stats["input"], 3) if stats["input"] else None
    if sc.expect:
        stats["phrase_seen"] = sc.expect in replies
    log.append(
        "\n## 數字\n\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=1) + "\n```\n"
    )
    return "\n".join(log), stats


SUMMARY_KEYS = (
    "seconds",
    "requests",
    "tool_calls",
    "input",
    "output",
    "cache_hit",
    "cost_usd",
    "stops",
    "outcomes",
    "cards",
    "phrase_seen",
    "crash",
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="anthropic,openai")
    ap.add_argument("--only", default="", help="逗號分隔的情境 key，例如 S2,S4")
    ap.add_argument("--port", type=int, default=8590)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    wanted = set(filter(None, a.only.split(",")))
    summary: list[dict[str, Any]] = []
    for offset, provider in enumerate(a.providers.split(",")):
        server = Server(a.port + offset, a.out / f"{provider}-server.log")
        try:
            server.wait()
            r = Runner(f"http://127.0.0.1:{server.port}")
            r.sign_in(provider)
            convs: dict[str, str] = {}
            for sc in SCENARIOS:
                if wanted and sc.key not in wanted:
                    continue
                cid = convs.get(sc.after) or str(uuid.uuid4())
                convs[sc.key] = cid
                print(f"== {provider} {sc.key} {sc.title}", flush=True)
                try:
                    md, stats = run_one(r, provider, sc, cid)
                except Exception as e:  # 一個情境壞了不拖垮其他的
                    md = f"# {provider} {sc.key}\n\n腳本出錯：{e!r}\n"
                    stats = {"provider": provider, "scenario": sc.key, "crash": repr(e)}
                (a.out / f"{provider}-{sc.key}.md").write_text(md)
                summary.append(stats)
                print("   ", {k: stats.get(k) for k in SUMMARY_KEYS if k in stats}, flush=True)
                (a.out / "summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=1)
                )
        finally:
            server.stop()
    head = "| 接口 | 情境 | 秒 | 輪 | 模型呼叫 | 工具 | input | 快取命中 | output | 網搜 | 費用 USD | 停止 | 工具結果 | 卡片 | 出現標記字樣 |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    rows = "".join(
        f"| {s['provider']} | {s['scenario']} | {s.get('seconds')} | {s.get('runs')} | {s.get('requests')} | {s.get('tool_calls')} | {s.get('input', 0):,} | {s.get('cache_hit')} | {s.get('output', 0):,} | {s.get('web_searches', 0) + s.get('tavily_searches', 0)} | {s.get('cost_usd')} | {' '.join(s.get('stops') or [])} | {s.get('outcomes') or s.get('crash')} | {s.get('cards')} | {s.get('phrase_seen', '')} |\n"
        for s in summary
    )
    (a.out / "summary.md").write_text(head + rows)
    print(head + rows)


if __name__ == "__main__":
    main()
