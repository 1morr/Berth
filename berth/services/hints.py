"""迴圈之間的提示：「有東西動了，去看看」（plan §3.2、票 11）。

背景迴圈之間要傳的東西比想像中少。plan §3.2 原文寫的是一條 `asyncio.Queue`，裡面裝
「請處理 job X」——但那句話的下半段是**「DB 狀態才是真相；程序重啟後由定時掃描補上」**，
而一旦掃描本來就找得到同一批 job，佇列裡的那個 hash 就不帶任何資訊了。

所以這裡是一個**沒有內容的喚醒訊號**：`planner_runner` 平常每 60 秒醒一次，poller 動了
任何一筆就 `nudge()` 讓它立刻醒。少掉的是佇列自己的三個問題——重複的 hash 要不要去重、
滿了要丟哪一筆、重啟之後裡面那幾筆誰來補；而掃描對這三件事的答案本來就是同一個。

一個程序一份（`main.py` 放進 `app.state`），與 `EventHub` 同一個道理：發訊號的是這個程序
裡的迴圈，等訊號的也是。
"""

from __future__ import annotations

import asyncio


class JobHints:
    """一個會自己合併的喚醒訊號。

    **合併是重點**：poller 一輪動了 40 筆 job，那也只是「去看看」一次——`planner_runner`
    的一輪本來就會把該處理的全部處理完。
    """

    def __init__(self) -> None:
        self._wake = asyncio.Event()

    def nudge(self) -> None:
        """有東西動了。**永不阻塞、永不丟例外**——呼叫端是背景迴圈。"""
        self._wake.set()

    async def wait(self, timeout: float) -> bool:
        """等一個提示，最多等 `timeout` 秒。回傳「是被叫醒的還是等到時間了」。

        兩種都要往下走：提示只是「早一點」，而定時醒來是重啟之後唯一的補課方式。
        """
        try:
            await asyncio.wait_for(self._wake.wait(), timeout)
        except TimeoutError:
            return False
        finally:
            # 清在這裡而不是叫醒之後：中間沒有任何 await，所以這一瞬間不會漏掉新的提示。
            self._wake.clear()
        return True
