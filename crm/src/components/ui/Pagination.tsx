import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "./Button";
import { useLanguage } from "../../contexts/LanguageContext";

type PaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

/** "Showing 21–40 of 57" plus Previous / Next, used under long tables. */
export default function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const { t } = useLanguage();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  return (
    <nav className="pagination-bar" aria-label={t("common.pagination.label")}>
      <span className="pagination-status" aria-live="polite">
        {t("common.pagination.range", { from, to, total })}
      </span>
      <div className="pagination-controls">
        <Button
          variant="secondary"
          size="sm"
          icon={<ChevronLeft size={14} />}
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          {t("common.pagination.previous")}
        </Button>
        <Button variant="secondary" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
          {t("common.pagination.next")}
          <ChevronRight size={14} aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
