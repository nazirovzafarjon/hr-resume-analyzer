import Button from "../ui/Button";
import EmptyState from "../ui/EmptyState";
import { SkeletonCards, SkeletonText } from "../ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";

/** Loading placeholder that keeps the page's shape (announced to screen readers). */
export function PortalLoading({ cards = false }: { cards?: boolean }) {
  const { t } = useLanguage();
  return (
    <div aria-busy="true">
      <p className="sr-only" role="status">
        {t("portal.loading")}
      </p>
      {cards ? <SkeletonCards count={4} /> : <SkeletonText lines={8} />}
    </div>
  );
}

/**
 * Load failure with context ("We couldn't load your applications") and a
 * retry, instead of a bare "Unexpected error".
 */
export function PortalError({ error, what, onRetry }: { error: unknown; what: string; onRetry: () => void }) {
  const { t } = useLanguage();
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <EmptyState
      tone="error"
      title={notFound ? t("portal.errors.notFoundTitle") : t("portal.errors.loadTitle", { what })}
      message={notFound ? t("portal.errors.notFoundMessage") : getErrorMessage(error, t("portal.errors.loadMessage"))}
      action={
        notFound ? (
          <Button variant="secondary" to="/candidate/applications">
            {t("portal.nav.applications")}
          </Button>
        ) : (
          <Button onClick={onRetry}>{t("common.retry")}</Button>
        )
      }
    />
  );
}
