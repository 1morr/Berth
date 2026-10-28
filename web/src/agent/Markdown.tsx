import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { INLINE_LINK } from '../components/controls'

/**
 * 助理回覆的 markdown（M5 票 12，`.scratch/m5/side-panel-shape.md`〈面板結構〉）。
 *
 * **消毒**：原始 HTML 不渲染（`skipHtml`），網址走 react-markdown 預設的 `urlTransform`（`javascript:`
 * 這類換成空的）。**圖片不載入**：圖片網址是常見的外洩通道（brief §14、研究 C4 第 6 點）——模型被外部
 * 內容誘導寫出帶著秘密的網址，瀏覽器一載入就送出去了；這裡只印「沒有載入」、替代文字與網址原文。
 *
 * 標題降成 `.label`：面板裡的 `h2` 是「助理」，回覆不該在文件大綱裡長出自己的章節。
 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="grid min-w-0 gap-2 text-sm break-words text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCjkAutolinks]}
        skipHtml
        allowedElements={ALLOWED}
        unwrapDisallowed
        components={COMPONENTS}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

/** markdown 語法樹裡用得到的那一小部分（mdast）。 */
interface Node {
  type: string
  value?: string
  url?: string
  children?: Node[]
}

/** 中日韓文字與全形標點：網址裡不會直接出現（瀏覽器會編碼），出現了就是網址已經結束。 */
const CJK = /[\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uff00-\uffef]/

/**
 * GFM 的自動連結只在空白處結束，中文句子沒有空白：「…bangumiId=3310，但我沒加」整段都進了網址
 * （票 22 critique 實跑抓到）。自動連結（字就是網址的那一種）在第一個中日韓字元處切開，後面的放回散文。
 * 寫成 `[字](網址)` 的連結不動。
 */
function remarkCjkAutolinks() {
  return (tree: Node) => {
    split(tree)
  }
}

function split(node: Node) {
  const children = node.children
  if (children === undefined) return
  for (let index = 0; index < children.length; index++) {
    const child = children[index]
    const text = child.children?.length === 1 ? child.children[0] : undefined
    const bare =
      child.type === 'link' && text?.type === 'text' && child.url?.endsWith(text.value ?? '\0')
    const at = bare ? (text?.value?.search(CJK) ?? -1) : -1
    if (bare && text?.value && at > 0) {
      const kept = text.value.slice(0, at)
      const rest = text.value.slice(at)
      child.url = child.url?.slice(0, child.url.length - text.value.length) + kept
      text.value = kept
      children.splice(index + 1, 0, { type: 'text', value: rest })
      continue
    }
    split(child)
  }
}

/**
 * 白名單（`.scratch/m5/side-panel-shape.md`〈面板結構〉）：其餘（task list 的勾選框、註腳）拆掉外殼、留下字。
 * `img` 在名單上，是為了交給下面的 `BlockedImage` 說「沒有載入」，不是畫出來。
 */
const ALLOWED = [
  'p',
  'br',
  'strong',
  'em',
  'del',
  'ul',
  'ol',
  'li',
  'code',
  'pre',
  'a',
  'img',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'blockquote',
  'hr',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
]

function Heading({ children }: { children?: ReactNode }) {
  return <p className="label text-ink">{children}</p>
}

function BlockedImage({ alt, src }: { alt?: string; src?: string | Blob }) {
  const { t } = useTranslation()
  return (
    <span className="my-1 grid gap-1 border-2 border-rule bg-well px-2 py-1.5">
      <span className="label text-ink-dim">{t('agent.imageBlocked')}</span>
      {alt ? <span className="text-xs text-ink">{alt}</span> : null}
      {typeof src === 'string' && src !== '' ? (
        <span className="value text-xs wrap-anywhere text-ink-dim">{src}</span>
      ) : null}
    </span>
  )
}

const COMPONENTS: Components = {
  h1: Heading,
  h2: Heading,
  h3: Heading,
  h4: Heading,
  h5: Heading,
  h6: Heading,
  p: ({ children }) => <p className="max-w-prose">{children}</p>,
  ul: ({ children }) => <ul className="grid list-disc gap-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="grid list-decimal gap-1 pl-5">{children}</ol>,
  a: ({ href, children }) =>
    href ? (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        // 散文裡的連結跟著散文排（`TEXT_LINK` 是 `.label` 的 inline-flex，換行時會與上下行疊在一起）。
        className={`${INLINE_LINK} wrap-anywhere`}
      >
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  img: ({ alt, src }) => <BlockedImage alt={alt} src={src} />,
  code: ({ children }) => (
    <code className="value bg-deck px-1 text-xs wrap-anywhere">{children}</code>
  ),
  // code block 裡那一段也是 `code`（沒寫語言時連 `className` 都沒有），行內那一塊 `deck` 底由這裡拿掉。
  pre: ({ children }) => (
    <pre className="value border-2 border-rule bg-hull px-2 py-1.5 text-xs whitespace-pre-wrap wrap-anywhere [&>code]:bg-transparent [&>code]:px-0">
      {children}
    </pre>
  ),
  // 寬表格只在自己那一格捲，不把面板撐寬（DESIGN.md〈手機〉）。
  table: ({ children }) => (
    <div className="max-w-full overflow-x-auto">
      <table className="border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-2 border-rule bg-deck px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => <td className="border-2 border-rule px-2 py-1 align-top">{children}</td>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-rule pl-3 text-ink-dim">{children}</blockquote>
  ),
  hr: () => <hr className="border-t-2 border-rule" />,
}
