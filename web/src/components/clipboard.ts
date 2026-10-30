/**
 * 把字放進剪貼簿，回傳成功與否。
 *
 * `navigator.clipboard` 只在 secure context（HTTPS、localhost）才有；區網 IP 走 HTTP 開 Berth 時
 * 它是 `undefined`，這時退回選取一塊暫時的 `<textarea>` 再 `execCommand('copy')`——舊 API，
 * 但瀏覽器在非 secure context 只剩這一條路。
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 沒權限或文件沒焦點：試舊方法。
    }
  }
  return copyBySelection(text)
}

function copyBySelection(text: string): boolean {
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  // 移出畫面外但仍可選取；`display: none` 選不到。
  area.style.position = 'fixed'
  area.style.top = '-1000px'
  area.style.opacity = '0'
  document.body.append(area)
  const active = document.activeElement
  try {
    area.focus()
    area.select()
    // `execCommand` 標了 deprecated，但非 secure context 沒有替代品。
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
    if (active instanceof HTMLElement) active.focus()
  }
}
