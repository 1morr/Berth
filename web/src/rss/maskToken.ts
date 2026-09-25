/** 網址裡的 `token=` 換成前四碼加省略號。Mikan 的聚合 feed 只靠它認人，整串就是憑證。 */
export function maskToken(url: string): string {
  return url.replace(/([?&]token=)([^&#]*)/i, (_, key: string, value: string) =>
    value.length > 4 ? `${key}${value.slice(0, 4)}…` : `${key}${value}`,
  )
}
