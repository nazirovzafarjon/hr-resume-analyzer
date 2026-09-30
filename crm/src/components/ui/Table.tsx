import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { SkeletonTable } from "./Skeleton";
import Pagination from "./Pagination";

export type TableColumn<T> = {
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
  /** Applied to the header cell (e.g. for right alignment or a fixed width). */
  headerClassName?: string;
  /** Provide a comparator to make this column sortable (client-side). */
  sort?: (a: T, b: T) => number;
  /** Server-side sort key; used instead of `sort` when `onSortChange` is set. */
  sortKey?: string;
  /** Hide on narrow screens to protect readability. */
  hideOnMobile?: boolean;
};

type TableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  /** Plain-text empty message (kept for backwards compatibility). */
  emptyLabel?: string;
  /** Preferred: a full <EmptyState /> for the "no data" case. */
  emptyState?: ReactNode;
  loading?: boolean;
  /** Skeleton row count while loading. */
  loadingRows?: number;
  compact?: boolean;
  /** Accessible description of the table's content. */
  caption?: string;
  /**
   * Paginate client-side after sorting (so a sort always applies to the whole
   * list, not just the visible page). Omit to render every row.
   */
  pageSize?: number;
  /**
   * Server-side sorting: the table only renders what the API returned and
   * reports header clicks, so a sort always applies to the whole dataset,
   * not just the loaded page.
   */
  serverSort?: { key: string; order: "asc" | "desc" };
  onSortChange?: (key: string) => void;
};

/**
 * The product's data table: hover rows, optional per-column sorting,
 * optional pagination, and built-in loading (skeleton) and empty states.
 *
 * Rows keep their natural width and the wrapper scrolls horizontally, so
 * information is never squeezed into unreadable columns on smaller screens.
 */
export default function Table<T>({
  columns,
  rows,
  rowKey,
  emptyLabel = "No records.",
  emptyState,
  loading = false,
  loadingRows = 5,
  compact = false,
  caption,
  pageSize,
  serverSort,
  onSortChange,
}: TableProps<T>) {
  const [sortIndex, setSortIndex] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const sortedRows = useMemo(() => {
    if (onSortChange || sortIndex === null) return rows;
    const comparator = columns[sortIndex]?.sort;
    if (!comparator) return rows;
    const copy = [...rows];
    copy.sort((a, b) => (sortDirection === "asc" ? comparator(a, b) : comparator(b, a)));
    return copy;
  }, [rows, columns, sortIndex, sortDirection, onSortChange]);

  // New rows (a filter or search changed) start again from the first page.
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [rows]);
  const totalPages = pageSize ? Math.max(1, Math.ceil(sortedRows.length / pageSize)) : 1;
  const safePage = Math.min(page, totalPages);
  const visibleRows = pageSize
    ? sortedRows.slice((safePage - 1) * pageSize, safePage * pageSize)
    : sortedRows;

  if (loading) {
    return (
      <div className="table-shell">
        <SkeletonTable rows={loadingRows} columns={Math.min(columns.length, 5)} />
      </div>
    );
  }

  if (rows.length === 0) {
    if (emptyState) return <>{emptyState}</>;
    return <p className="table-empty">{emptyLabel}</p>;
  }

  function toggleSort(index: number) {
    if (index === sortIndex) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortIndex(index);
    setSortDirection("asc");
  }

  return (
    <>
    <div className="table-wrap">
      <table className={`table table--stack${compact ? " table--compact" : ""}`}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column, index) => {
              const serverSorted = Boolean(onSortChange && column.sortKey);
              const isSorted = serverSorted
                ? serverSort?.key === column.sortKey
                : sortIndex === index;
              const direction = serverSorted ? serverSort?.order : sortDirection;
              const sortable = onSortChange ? serverSorted : Boolean(column.sort);
              return (
                <th
                  key={column.header}
                  scope="col"
                  className={[column.headerClassName, column.hideOnMobile ? "table-col--hide-mobile" : null]
                    .filter(Boolean)
                    .join(" ") || undefined}
                  aria-sort={
                    isSorted ? (direction === "asc" ? "ascending" : "descending") : undefined
                  }
                >
                  {sortable ? (
                    <button
                      type="button"
                      className="table-sort-button"
                      onClick={() =>
                        serverSorted ? onSortChange?.(column.sortKey as string) : toggleSort(index)
                      }
                    >
                      {column.header}
                      <span aria-hidden="true">
                        {isSorted ? (
                          direction === "asc" ? (
                            <ArrowUp size={12} />
                          ) : (
                            <ArrowDown size={12} />
                          )
                        ) : (
                          <ChevronsUpDown size={12} opacity={0.45} />
                        )}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td
                  key={column.header}
                  data-label={column.header}
                  className={[column.className, column.hideOnMobile ? "table-col--hide-mobile" : null]
                    .filter(Boolean)
                    .join(" ") || undefined}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {pageSize && sortedRows.length > pageSize && (
      <Pagination page={safePage} pageSize={pageSize} total={sortedRows.length} onPageChange={setPage} />
    )}
    </>
  );
}
