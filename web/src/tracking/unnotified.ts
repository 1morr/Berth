import type { MyNotify } from '../api/notify'

/**
 * 這位管理員收不收得到遲到（M5.5 票 12；ADR-0015：通知只走 Discord 私訊）。遲到走「有 N 件等你處理」，
 * 所以要四件都齊：管理員設好了 bot、這個人填了 Discord ID、勾了「等你處理」、上一次送給他時 Discord 沒說到不了。
 * 少一件就收不到，追更頁頁首說一句。讀 `GET /me/notifications` 就夠，不加端點。
 */
export function unnotified(mine: MyNotify): boolean {
  return (
    !mine.bot_configured ||
    mine.discord_user_id === '' ||
    !mine.kinds.includes('waiting') ||
    mine.unreachable_at !== null
  )
}
