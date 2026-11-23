/**
 * Read every page of a skip/limit list endpoint.
 *
 * The list endpoints cap a single response (applications: 50 by default, at
 * most 200; interviews: 100 / 500). Pages that filter, search and count on the
 * client need the whole set, otherwise anything past the first page silently
 * disappears from the table and the KPI tiles.
 *
 * Rows are de-duplicated by `id`: a record created while the pages are being
 * read shifts the offsets by one, which would otherwise repeat a row.
 */
export async function fetchAllPages<T extends { id: number }>(
  fetchPage: (skip: number, limit: number) => Promise<T[]>,
  pageSize: number,
  /** Safety stop so a misbehaving endpoint can never loop forever. */
  maxPages = 100,
): Promise<T[]> {
  const rows: T[] = [];
  const seen = new Set<number>();
  for (let page = 0; page < maxPages; page += 1) {
    const batch = await fetchPage(page * pageSize, pageSize);
    for (const row of batch) {
      if (seen.has(row.id)) continue;
      seen.add(row.id);
      rows.push(row);
    }
    if (batch.length < pageSize) break;
  }
  return rows;
}
