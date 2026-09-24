/**
 * 讀取中的一格：海報位留一個空位，標識帶留幾條線。**不會動**——這個世界沒有骨架屏動畫。
 *
 * **標識帶的高度與真的那一格一樣**（票 13）：內距、行距、每一行的高度都照 `MediaTile` / `Tile` 抄，
 * 線畫在同高的格子裡。差幾 px 的話，資料到的那一刻第二排以下整排往下推，那也是版面位移。
 * 媒體庫牆的卡片多兩行（觀看、盤點）與最下面一條 Jellyfin 行（`inventory`）。
 */
export function TilePlaceholder({ inventory = false }: { inventory?: boolean }) {
  return (
    <div className="grid grid-rows-[auto_1fr] border-2 border-rule bg-well" aria-hidden="true">
      <div className="aspect-[2/3] bg-hull" />
      <div className="grid content-start gap-1 px-3 py-2.5">
        <PlaceholderLine className="h-4 w-12" />
        <PlaceholderLine className="h-10 w-4/5" />
        {inventory && (
          <>
            <PlaceholderLine className="h-4 w-1/2" />
            <PlaceholderLine className="h-4 w-1/3" />
          </>
        )}
      </div>
      {inventory && <div className="min-h-10 border-t-2 border-rule" />}
    </div>
  )
}

/**
 * 一行字的位置：線本身細，畫在與那一行同高的格子頂端。高度由呼叫端給（`h-4` 是 `text-xs` 的一行、`h-5` 是
 * `text-sm` 的一行），空位格才與真的那一格一樣高。
 */
function PlaceholderLine({ className }: { className: string }) {
  return (
    <span className={`block ${className}`}>
      <span className="mt-1 block h-2 w-full bg-deck" />
    </span>
  )
}
