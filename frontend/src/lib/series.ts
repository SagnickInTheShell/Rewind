/** Index of the last element with key ≤ t (binary search); -1 if none. */
export function indexAtOrBefore<T>(items: T[], t: number, key: (x: T) => number): number {
  let lo = 0;
  let hi = items.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (key(items[mid]) <= t + 1e-9) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans;
}

export function valueAt<T>(items: T[], t: number, key: (x: T) => number): T | undefined {
  if (!items.length) return undefined;
  const i = indexAtOrBefore(items, t, key);
  return items[Math.max(i, 0)];
}

/** Group items by a string key, preserving order. */
export function groupBy<T>(items: T[], key: (x: T) => string): Map<string, T[]> {
  const m = new Map<string, T[]>();
  for (const it of items) {
    const k = key(it);
    const arr = m.get(k);
    if (arr) arr.push(it);
    else m.set(k, [it]);
  }
  return m;
}

export function centroid(pts: { x: number; y: number }[]): { x: number; y: number } {
  const n = Math.max(pts.length, 1);
  return { x: pts.reduce((a, p) => a + p.x, 0) / n, y: pts.reduce((a, p) => a + p.y, 0) / n };
}
