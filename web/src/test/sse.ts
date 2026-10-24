/**
 * 助理的 SSE 回應替身（M5 票 08）：一行 `data:` 一個 chunk，同後端 `api/conversations.py`。
 *
 * `held()` 回一條還沒寫完的串流：測試先 `push` 幾個 chunk、看畫面，再 `push` `finish` 收尾。
 */

import type { Chunk } from '../api/assistant'

const encoder = new TextEncoder()

function line(chunk: Chunk): Uint8Array {
  return encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`)
}

function sse(body: ReadableStream<Uint8Array>): Response {
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

/** 一次寫完的整段回覆。 */
export function streamed(...chunks: Chunk[]): () => Response {
  return () =>
    sse(
      new ReadableStream({
        start(controller) {
          for (const chunk of chunks) controller.enqueue(line(chunk))
          controller.close()
        },
      }),
    )
}

/** 停在半路的回覆。 */
export function held() {
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined
  const body = new ReadableStream<Uint8Array>({
    start(opened) {
      controller = opened
    },
  })
  return {
    respond: () => sse(body),
    push(chunk: Chunk) {
      controller?.enqueue(line(chunk))
      if (chunk.type === 'finish') controller?.close()
    },
  }
}
