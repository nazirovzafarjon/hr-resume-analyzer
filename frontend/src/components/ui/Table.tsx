import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { SkeletonTable } from "./Skeleton";

export type TableColumn<T> = {
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
  /** Applied to the header cell (e.g. for right alignment or a fixed width). */
  headerClassName?: string;
  /** Provide a comparator to make this column sortable. */
  sort?: (a: T, b: T) => number;
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
};

/**
 * The product's data table: sticky header, hover rows, optional per-column
 * sorting, and built-in loading (skeleton) and empty states.
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
}: TableProps<T>) {
  const [sortIndex, setSortIndex] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const sortedRows = useMemo(() => {
    if (sortIndex === null) return rows;
    const comparator = columns[sortIndex]?.sort;
    if (!comparator) return rows;
    const copy = [...rows];
    copy.sort((a, b) => (sortDirection === "asc" ? comparator(a, b) : comparator(b, a)));
    return copy;
  }, [rows, columns, sortIndex, sortDirection]);

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
    <div className="table-wrap">
      <table className={`table${compact ? " table--compact" : ""}`}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column, index) => {
              const isSorted = sortIndex === index;
              const sortable = Boolean(column.sort);
              return (
                <th
                  key={column.header}
                  scope="col"
                  className={column.headerClassName}
                  aria-sort={
                    isSorted ? (sortDirection === "asc" ? "ascending" : "descending") : undefined
                  }
                >
                  {sortable ? (
                    <button
                      type="button"
                      className="table-sort-button"
                      onClick={() => toggleSort(index)}
                    >
                      {column.header}
                      <span aria-hidden="true">
                        {isSorted ? (
                          sortDirection === "asc" ? (
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
          {sortedRows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.header} className={column.className}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
