# 一次性但保留（plan §10）：換模型、或之後要再決定留不留某個資料來源時重量。
# 中文的情境句子寫成長字串比較好讀，不照行寬折。
# ruff: noqa: E501
"""實驗：側面板的資料來源要不要留（2026-10-28），之後拿來量「產品現在的樣子」。

- 2026-10-28 比的是「完整組」（當時的產品，多 AniList 的搜尋與系列走圖、Fribb）對「精簡組」（只有 TMDB 與
  網路搜尋，加 AniList 季表與 Bangumi 給新番推薦）；結論是精簡組，`docs/research/agent-sources-ab-2026-10-28.md`。
- M5 票 23d 之後產品就是精簡組：演練情境 `agent-live`。當時的 `agent-live-lean` 情境與那份精簡 skill 的副本
  拿掉了（產品已經是它），完整組也不在了，要重比得從 git 歷史拿回來。
- 網路搜尋：Anthropic 接口只用伺服器端 `web_search`（不給 Tavily key），OpenAI 接口用 Tavily；
  `--no-tavily` 讓 OpenAI 接口也不給，量沒有網搜時的樣子（票 23d）。

題目是新番推薦與三部整系列（Re:Zero、無職轉生、HxH 2011），每組每題每種接口兩次；**只跑到確認卡出現**
（不按、不送單）。模型問 Route 或來源時給一次固定回答。每一次（組 × 接口 × 重複）一台全新的 Berth，
兩組交錯跑，尖峰離峰的價差兩組各半。累計費用到 `--budget` 就停。

    uv run --env-file .env python scripts/experiments/agent_sources_ab.py

結果寫到 `--out`（預設 `.local/experiments/results/agent_sources_ab/`）：每一次一份逐字稿、`results.json`。
對錯（季集對不對、有沒有標出不確定）不在這裡判，讀逐字稿對 `docs/research/fribb-vs-chaining-2026-10-28.json`。
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m5_acceptance_scenarios import (
    ANSWER,
    ROOT,
    Runner,
    Server,
    render,
    reply_text,
    run_ids,
)

OUT = ROOT / ".local" / "experiments" / "results" / "agent_sources_ab"
#: 組名 → 演練情境。`lean` 是 2026-10-28 的精簡組，現在就是產品；逐字稿的檔名照舊帶它。
GROUPS = {"lean": "agent-live"}
#: 完成與等確認之外的停止原因都是防護（或出錯）停下的。
NORMAL_STOPS = {"completed", "awaiting_confirmation"}


@dataclass(frozen=True)
class Task:
    key: str
    steps: tuple[str, ...]


def franchise(title: str) -> Task:
    return Task(
        "",
        (
            f"幫我下載{title}全系列（不要短篇）。先列清單給我看，不要直接送。",
            "清單上的都要，幫我找來源，一次送單。",
            ANSWER,
        ),
    )


TASKS = (
    Task(
        "picks",
        (
            "推薦這一季（2026 年秋季）評價好的新番動畫 5 部，附評分與評分人數，說明為什麼推薦。",
            "第一部幫我安排：還在播的話幫我訂閱，播完了就找來源下載。",
            ANSWER,
        ),
    ),
    Task("rezero", franchise(" Re:Zero ").steps),
    Task("mushoku", franchise("《無職轉生》").steps),
    Task("hxh2011", franchise("《HUNTER×HUNTER》2011 年版").steps),
)

#: `--set more`：`docs/research/fribb-vs-chaining-2026-10-28.json` 裡其餘 14 部（補跑精簡組，看有沒有退步）。
#: 鍵與那份研究的 `series` 相同；撞名的重製版照 HxH 的寫法說年份。
MORE_TASKS = tuple(
    Task(key, franchise(title).steps)
    for key, title in (
        ("jujutsu", "《咒術迴戰》"),
        ("frieren", "《葬送的芙莉蓮》"),
        ("dandadan", "《膽大黨》"),
        ("aot", "《進擊的巨人》"),
        ("kaguya", "《輝夜姬想讓人告白》"),
        ("spyfamily", "《SPY×FAMILY 間諜家家酒》"),
        ("bleach", "《BLEACH 死神》"),
        ("uchouten", "《有頂天家族》"),
        ("maou", "《打工吧！魔王大人》"),
        ("fruitsbasket", "《水果籃子》2019 年版"),
        ("urusei", "《福星小子》2022 年版"),
        ("kino", "《奇諾之旅》2017 年版"),
        ("tamako", "《玉子市場》"),
        ("abyss", "《來自深淵》"),
    )
)
SETS = {"main": TASKS, "more": MORE_TASKS}


def run_task(
    r: Runner, task: Task, label: str, *, list_only: bool = False
) -> tuple[str, dict[str, Any]]:
    """逐句送出，確認卡一出現就停（不按）。`list_only` 只送第一句（先列清單）。"""
    cid = str(uuid.uuid4())
    log = [f"# {label} · {task.key}\n", f"對話 `{cid}`。\n"]
    runs: list[str] = []
    replies: list[str] = []
    card: dict[str, Any] | None = None
    started = time.monotonic()
    for step in task.steps[:1] if list_only else task.steps:
        log.append(f"\n## 👤 {step}\n")
        chunks = r.say(cid, step)
        log.extend(render(chunks))
        runs.extend(run_ids(chunks))
        replies.append(reply_text(chunks))
        if any(c.get("type") == "http-error" for c in chunks):
            break
        asks = [c for c in chunks if c.get("type") == "tool-approval-request"]
        if asks:
            found = {p["tool_call_id"]: p for p in r.proposals(cid)}
            cards = [found[a["toolCallId"]] for a in asks if a["toolCallId"] in found]
            card = cards[0] if cards else {"missing": True}
            for each in cards:
                log.append(
                    f"> 🟨 **確認卡**（停在這裡，不按）`{each['command']}`，{len(each['arguments'])} 列\n"
                    + "".join(
                        f"> - `{json.dumps(args, ensure_ascii=False)[:300]}`\n"
                        for args in each["arguments"]
                    )
                )
            break
    seconds = round(time.monotonic() - started)
    details = [r.run(run_id) for run_id in dict.fromkeys(runs)]
    tools = [tool for run in details for step in run["steps"] for tool in step["tools"]]
    known = [run["cost_usd"] for run in details if run["cost_usd"] is not None]
    stats: dict[str, Any] = {
        "task": task.key,
        "conv": cid,
        "seconds": seconds,
        "turns": len(details),
        "requests": sum(run["requests"] for run in details),
        "tool_calls": sum(run["tool_calls"] for run in details),
        "input": sum(run["input_tokens"] for run in details),
        "output": sum(run["output_tokens"] for run in details),
        "cache_read": sum(run["cache_read_tokens"] or 0 for run in details),
        "web_searches": sum(run["web_searches"] for run in details),
        "tavily_searches": sum(run["tavily_searches"] for run in details),
        "cost_usd": round(sum(known), 5),
        "cost_unknown_turns": len(details) - len(known),
        "stops": [run["stop_reason"] for run in details],
        "guard_stops": [
            run["stop_reason"] for run in details if run["stop_reason"] not in NORMAL_STOPS
        ],
        "tools": [t["command"] for t in tools],
        "tool_outcomes": {
            o: sum(1 for t in tools if t["outcome"] == o)
            for o in sorted({t["outcome"] for t in tools})
        },
        "card": None
        if card is None
        else {"command": card.get("command"), "rows": card.get("arguments")},
        # 每一輪（使用者的一句）：input 合計、每次呼叫的 input（看上下文怎麼長）、搜了幾次、
        # 種子搜了幾次、截斷了幾筆、為什麼停（票 23d 量「找種子那一輪」用）。
        "per_turn": [
            {
                "input": run["input_tokens"],
                "call_inputs": [s["call"]["input_tokens"] for s in run["steps"] if s["call"]],
                "requests": run["requests"],
                "web_searches": run["web_searches"],
                "tavily_searches": run["tavily_searches"],
                "torrent_searches": sum(
                    t["command"] == "search.search_torrents"
                    for s in run["steps"]
                    for t in s["tools"]
                ),
                "truncated": sum(t["truncated"] for s in run["steps"] for t in s["tools"]),
                "stop": run["stop_reason"],
            }
            for run in details
        ],
        "user_turns_used": len(replies),
    }
    log.append(
        "\n## 數字\n\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=1) + "\n```\n"
    )
    return "\n".join(log), stats


def sign_in(r: Runner, provider: str, *, tavily: bool) -> None:
    """登入並填 AI 設定。測試連線偶爾逾時（服務商那一端），再試兩次。"""
    for attempt in range(3):
        try:
            r.sign_in(provider, tavily=tavily and provider == "openai")
            return
        except RuntimeError:
            if attempt == 2:
                raise
            time.sleep(15)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="anthropic,openai")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--only", default="", help="逗號分隔的題目 key，例如 rezero,hxh2011")
    ap.add_argument(
        "--set", choices=sorted(SETS), default="main", help="main：原本四題；more：其餘 14 部"
    )
    ap.add_argument("--groups", default="lean")
    ap.add_argument(
        "--no-tavily", action="store_true", help="OpenAI 接口也不給 Tavily key（沒有網搜）"
    )
    ap.add_argument("--list-only", action="store_true", help="整部系列只送「先列清單」那一句")
    ap.add_argument("--budget", type=float, default=1.5, help="累計估計費用（USD）到這裡就停")
    ap.add_argument("--port", type=int, default=8600)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    wanted = set(filter(None, a.only.split(",")))
    # 接續：同一個 `--out` 裡已經跑完（沒出錯）的不重跑，費用接著算（中途斷線時不必重花一次）。
    saved = a.out / "results.json"
    previous = json.loads(saved.read_text()) if saved.exists() else {"runs": []}
    results: list[dict[str, Any]] = [run for run in previous["runs"] if "crash" not in run]
    done = {(run["rep"], run["provider"], run["group"], run["task"]) for run in results}
    spent = sum(run.get("cost_usd") or 0.0 for run in results)
    port = a.port
    stopped = ""
    for rep in range(1, a.reps + 1):
        for provider in a.providers.split(","):
            for group in a.groups.split(","):
                scenario = GROUPS[group]
                if stopped:
                    break
                label = f"r{rep}-{provider}-{group}" + ("-notavily" if a.no_tavily else "")
                todo = [
                    task
                    for task in SETS[a.set]
                    if (not wanted or task.key in wanted)
                    and (rep, provider, group, task.key) not in done
                ]
                if not todo:
                    continue
                server = Server(port, a.out / f"{label}-server.log", scenario)
                port += 1
                try:
                    server.wait()
                    r = Runner(f"http://127.0.0.1:{server.port}")
                    sign_in(r, provider, tavily=not a.no_tavily)
                    for task in todo:
                        if spent >= a.budget:
                            stopped = f"budget ${a.budget} reached before {label} {task.key}"
                            break
                        print(f"== {label} {task.key} (spent ${spent:.4f})", flush=True)
                        try:
                            md, stats = run_task(r, task, label, list_only=a.list_only)
                        except Exception as e:  # 一題壞了不拖垮其他的
                            md, stats = (
                                f"# {label} {task.key}\n\n腳本出錯：{e!r}\n",
                                {"task": task.key, "crash": repr(e)},
                            )
                        stats |= {"rep": rep, "provider": provider, "group": group}
                        spent += stats.get("cost_usd") or 0.0
                        (a.out / f"{label}-{task.key}.md").write_text(md)
                        results.append(stats)
                        print(
                            "   ",
                            {
                                k: stats.get(k)
                                for k in (
                                    "seconds",
                                    "requests",
                                    "tool_calls",
                                    "input",
                                    "output",
                                    "web_searches",
                                    "tavily_searches",
                                    "cost_usd",
                                    "guard_stops",
                                    "crash",
                                )
                            },
                            "card" if stats.get("card") else "no card",
                            flush=True,
                        )
                        (a.out / "results.json").write_text(
                            json.dumps(
                                {"spent_usd": round(spent, 5), "stopped": stopped, "runs": results},
                                ensure_ascii=False,
                                indent=1,
                            )
                        )
                finally:
                    server.stop()
    (a.out / "results.json").write_text(
        json.dumps(
            {"spent_usd": round(spent, 5), "stopped": stopped, "runs": results},
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"spent ${spent:.4f}; stopped: {stopped or 'no'}")


if __name__ == "__main__":
    main()
