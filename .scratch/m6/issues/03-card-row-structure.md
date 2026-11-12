# 03 — 確認卡改列結構

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉M5.6 遺留第 3 點、〈共同規則〉；`.scratch/m5.6/issues/10-m5.6-ui-wrap-up.md`〈沒修〉；M5.6 票 03 的 Comments；brief §14〈對話裡的確認卡〉；plan §7〈確認卡〉；`DESIGN.md`〈側面板〉

## 為什麼

M5.6 票 03 把 Route 改成一部作品選一次，但列的結構沒動：每一列仍重述作品與 Route，同一集的多個版本沒有標，也沒照季集排序。13 列的卡要從頭讀到尾才看得出送了什麼。

## 做什麼

1. 走 `/impeccable`（`shape` 這張卡的新結構，再實作）。
2. 依作品分組：作品名、Route、資料夾每組印一次；列只留發佈名、大小、已有的集。這會推翻票 03 的「列裡重述 Route」，vitest 與 e2e 跟著改。
3. 照季集排序；同一集有不只一列時標出來（預覽要多帶「這一列蓋到哪幾集」，伺服器算）。
4. 全選／全不選、按作品收合。
5. 字幕組的 `Options` 改成 `role="radiogroup"`，選中態加非顏色訊號；`/rss` 也用這個元件，一起看。
6. 〈沒修〉清單裡其他的項目（按過的卡收成摘要、拒絕時給原因、同名卡的 region 名稱、相對期限、第一輪在字幕組選定後才展開）：做或不做逐條寫進 Comments。
7. **M5.6 沒人接的兩項**（2026-11-12 M5.6 回顧，使用者同意）：`web/src/agent/ConfirmCard.tsx` 已 1286 行，改結構時照卡片種類拆檔；長卡貼底的確認列在面板 24rem 與 40rem 寬會壓到列（M5.6 票 10b audit），一起修。
8. 文件：plan §7〈確認卡〉、brief §14、`DESIGN.md`。

## 驗收

- [ ] 卡片依作品分組、照季集排序、同一集的多列有標記（vitest）
- [ ] 全選與按作品收合用得到，鍵盤操作得到（playwright，桌機與 390px，附截圖）
- [ ] 字幕組選項是 radiogroup，`/rss` 的訂閱流程照常（vitest 與 e2e）
- [ ] 〈沒修〉清單逐條有結論
- [ ] `ConfirmCard.tsx` 拆檔；24rem 與 40rem 寬的長卡，確認列不壓到列（playwright 截圖）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠

## Comments
