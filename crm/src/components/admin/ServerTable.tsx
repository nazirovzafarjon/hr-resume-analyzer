import Button from "../ui/Button";
import EmptyState from "../ui/EmptyState";
import Pagination from "../ui/Pagination";
import Table, { type TableColumn } from "../ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";
import type { Page } from "../../types/admin";

type ServerTableProps<T> = {
  columns: TableColumn<T>[];
  data: Page<T> | null;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  rowKey: (row: T) => string | number;
  caption: string;
  onPageChange: (page: number) => void;
  sort?: { key: string; order: "asc" | "desc" };
  onSortChange?: (key: string) => void;
  /** Whether any filter is active (switches the empty state wording). */
  filtered: boolean;
  onClearFilters: () => void;
  emptyTitle: string;
  emptyMessage: string;
};

/**
 * A server-paginated admin table: the rows of one API page, the pagination
 * bar under them, and the loading / error (with retry) / empty states.
 *
 * On the first load a skeleton is shown; on later loads (page or filter
 * changes) the previous rows stay visible until the new page arrives.
 */
export default function ServerTable<T>({
  columns,
  data,
  loading,
  error,
  onRetry,
  rowKey,
  caption,
  onPageChange,
  sort,
  onSortChange,
  filtered,
  onClearFilters,
  emptyTitle,
  emptyMessage,
}: ServerTableProps<T>) {
  const { t } = useLanguage();

  if (error) {
    return (
      <EmptyState
        tone="error"
        title={t("errors.loadTitle")}
        message={getErrorMessage(error, t("errors.loadMessage"))}
        action={
          <Button variant="secondary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  return (
    <div className={loading && data ? "server-table is-refreshing" : "server-table"} aria-busy={loading}>
      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={rowKey}
        loading={loading && !data}
        caption={caption}
        serverSort={sort}
        onSortChange={onSortChange}
        emptyState={
          filtered ? (
            <EmptyState
              title={t("empty.noMatchingTitle")}
              message={t("empty.noMatchingMessage")}
              action={
                <Button variant="secondary" onClick={onClearFilters}>
                  {t("common.clearFilters")}
                </Button>
              }
            />
          ) : (
            <EmptyState title={emptyTitle} message={emptyMessage} />
          )
        }
      />
      {data && data.total > data.limit && (
        <Pagination page={data.page} pageSize={data.limit} total={data.total} onPageChange={onPageChange} />
      )}
    </div>
  );
}
