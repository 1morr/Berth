import type { Page } from '@playwright/test'

/**
 * 版面的量尺（M4 票 119）。函式本體是字串：e2e 的 tsconfig 沒有 DOM 型別，這幾行在瀏覽器裡跑。
 *
 * 量尺收一段選填的 `change`：`apply` 改 DOM、量完 `undo` 改回去，三步在同一個同步的 evaluate 裡，
 * React 沒有機會在中間重繪。閘門用它在測試裡做雙向變異：造一個違規證明量尺會紅，改一次無關的樣式證明它不會。
 */

interface DomChange {
  /** 在頁面裡跑的敘述；宣告的變數 `undo` 看得到。 */
  apply: string
  undo: string
}

const NO_CHANGE: DomChange = { apply: '', undo: '' }

/**
 * 頁面捲到頂時，`main` 裡上下相鄰兩樣看得到的東西（有字的元素、控制項）之間最大的空白（px），與頁面有沒有
 * 橫向溢出。固定在底部的列量的是它當下畫在哪裡，不是它在文件流裡的位置。
 */
export async function blankAndOverflow(
  page: Page,
  change = NO_CHANGE,
): Promise<{ viewport: number; blank: number; overflow: boolean }> {
  await page.evaluate('window.scrollTo(0, 0)')
  return page.evaluate(`(() => {
    ${change.apply}
    const main = document.querySelector('main')
    const spans = []
    for (const element of main.querySelectorAll('*')) {
      const own = [...element.childNodes].some((node) => node.nodeType === 3 && node.textContent.trim())
      const control = element.matches('input, select, textarea, button, img, svg')
      if (!own && !control) continue
      const rect = element.getBoundingClientRect()
      if (rect.height === 0 || rect.width === 0) continue
      spans.push([rect.top + scrollY, rect.bottom + scrollY])
    }
    spans.sort((a, b) => a[0] - b[0])
    let blank = 0
    let reach = spans.length > 0 ? spans[0][1] : 0
    for (const [top, bottom] of spans) {
      blank = Math.max(blank, top - reach)
      reach = Math.max(reach, bottom)
    }
    const measured = {
      viewport: innerHeight,
      blank: Math.round(blank),
      overflow: document.documentElement.scrollWidth > innerWidth,
    }
    ${change.undo}
    return measured
  })()`)
}
