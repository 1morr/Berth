/** 按了一顆之後的那一組：有就拿掉，沒有就加上。 */
export function toggled<T>(selected: ReadonlySet<T>, value: T): ReadonlySet<T> {
  const after = new Set(selected)
  if (!after.delete(value)) after.add(value)
  return after
}
