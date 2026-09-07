"""命令（use case）：所有會改變狀態的操作都在這裡（plan §1.3）。

交易邊界屬於呼叫端：命令收 `AsyncSession`、做事、**不 commit**。
API 與 pipeline 各自決定一次請求或一次迴圈是不是一個工作單元。
"""
