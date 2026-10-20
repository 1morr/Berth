import type { Page } from '@playwright/test'

/**
 * 版面的量尺（M4 票 119）。函式本體是字串：e2e 的 tsconfig 沒有 DOM 型別，這幾行在瀏覽器裡跑。
 */

/**
 * `StepFrame` 兩欄各自的內容高度（px）。grid 會把兩欄拉成一樣高，所以量的是欄裡最後一個子元素的
 * 底邊加上欄的下內距，不是欄本身。
 */
export async function frameColumns(page: Page): Promise<number[]> {
  return page.evaluate(`(() => {
    const heights = [...document.querySelectorAll('[data-frame-column]')].map((column) => {
      const top = column.getBoundingClientRect().top
      const bottom = Math.max(...[...column.children].map((child) => child.getBoundingClientRect().bottom))
      return Math.round(bottom - top + parseFloat(getComputedStyle(column).paddingBottom))
    })
    return heights
  })()`)
}

/**
 * 頁面捲到頂時，`main` 裡上下相鄰兩樣看得到的東西（有字的元素、控制項）之間最大的空白（px），與頁面有沒有
 * 橫向溢出。固定在底部的列量的是它當下畫在哪裡，不是它在文件流裡的位置。
 */
export async function blankAndOverflow(
  page: Page,
): Promise<{ viewport: number; blank: number; overflow: boolean }> {
  await page.evaluate('window.scrollTo(0, 0)')
  return page.evaluate(`(() => {
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
    return {
      viewport: innerHeight,
      blank: Math.round(blank),
      overflow: document.documentElement.scrollWidth > innerWidth,
    }
  })()`)
}
