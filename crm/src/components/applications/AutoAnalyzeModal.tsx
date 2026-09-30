import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Select from "../forms/Select";
import TextInput from "../forms/TextInput";
import { useLanguage } from "../../contexts/LanguageContext";
import type {
  AutoAnalyzeFilterOption,
  AutoAnalyzeProgressResponse,
} from "../../services/applicationsService";
import {
  getAutoAnalyzeAvailable,
  startAutoAnalyze,
  getAutoAnalyzeProgress,
  cancelAutoAnalyze,
} from "../../services/applicationsService";
import { getErrorMessage } from "../../utils/apiError";

type ModalState = "setup" | "running" | "completed";
type Order = "oldest" | "newest";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Job selected in the Applications filter; limits the batch to it. */
  jobId?: number;
  /** Called after a batch ran, so the page can reload its table. */
  onFinished?: () => void;
};

const MAX_BATCH = 1000;
const POLL_MS = 2000;
const ALL = "";

/** Parse the count field strictly: whole numbers 1–1000 only. */
function parseCount(raw: string): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw);
  return value >= 1 && value <= MAX_BATCH ? value : null;
}

/**
 * Auto Analyze: HR picks the processing order, how many resumes, and
 * optionally a company/position. The server selects the matching new,
 * never-analysed applications and analyses them one by one in the
 * background; this dialog shows the real progress it reports.
 */
export default function AutoAnalyzeModal({ open, onClose, jobId, onFinished }: Props) {
  const { t } = useLanguage();
  const [state, setState] = useState<ModalState>("setup");
  const [order, setOrder] = useState<Order>("newest");
  const [count, setCount] = useState("50");
  const [company, setCompany] = useState(ALL);
  const [position, setPosition] = useState(ALL);
  const [options, setOptions] = useState<AutoAnalyzeFilterOption[]>([]);
  const [availableCount, setAvailableCount] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [remainingAfter, setRemainingAfter] = useState(0);
  const [progress, setProgress] = useState<AutoAnalyzeProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const ranBatch = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Reset whenever the dialog opens.
  useEffect(() => {
    if (!open) return;
    setState("setup");
    setError(null);
    setCompany(ALL);
    setPosition(ALL);
    setBatchId(null);
    setProgress(null);
    ranBatch.current = false;
  }, [open]);

  // Count matching applications for the current filters (server-side).
  useEffect(() => {
    if (!open || state !== "setup") return;
    let cancelled = false;
    setAvailableCount(null);
    getAutoAnalyzeAvailable({ job_id: jobId, company, position })
      .then((res) => {
        if (cancelled) return;
        setAvailableCount(res.count);
        setOptions(res.options);
      })
      .catch(() => {
        if (!cancelled) setError(t("applications.autoAnalyzeModal.loadCountFailed"));
      });
    return () => {
      cancelled = true;
    };
  }, [open, state, jobId, company, position, t]);

  useEffect(() => stopPolling, [stopPolling]);

  const companies = useMemo(
    () => [...new Set(options.map((option) => option.company_name))],
    [options],
  );
  const positions = useMemo(
    () => [
      ...new Set(
        options
          .filter((option) => company === ALL || option.company_name === company)
          .map((option) => option.position),
      ),
    ],
    [options, company],
  );

  const pollOnce = useCallback(
    async (id: number) => {
      try {
        const p = await getAutoAnalyzeProgress(id);
        setProgress(p);
        if (p.status === "completed" || p.status === "cancelled" || p.status === "failed") {
          stopPolling();
          setState("completed");
        }
      } catch {
        /* keep polling; a transient error must not end the view */
      }
    },
    [stopPolling],
  );

  const handleStart = async () => {
    const countNum = parseCount(count);
    if (countNum === null) {
      setError(t("applications.autoAnalyzeModal.integerError"));
      return;
    }
    setError(null);
    setStarting(true);
    try {
      const res = await startAutoAnalyze({
        count: countNum,
        order,
        job_id: jobId,
        company: company || undefined,
        position: position || undefined,
      });
      ranBatch.current = true;
      setBatchId(res.batch_id);
      setRemainingAfter(res.remaining_count);
      setProgress({
        batch_id: res.batch_id,
        status: res.status,
        total: res.selected_count,
        processed: 0,
        successful: 0,
        failed: 0,
        skipped: 0,
        remaining: res.selected_count,
        current_application_id: null,
        created_at: null,
        finished_at: null,
      });
      setState("running");
      stopPolling();
      pollRef.current = window.setInterval(() => pollOnce(res.batch_id), POLL_MS);
    } catch (err: unknown) {
      setError(getErrorMessage(err, t("applications.autoAnalyzeModal.startFailed")));
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    if (batchId === null) return;
    try {
      await cancelAutoAnalyze(batchId);
    } catch {
      /* the next poll shows the real state */
    }
    await pollOnce(batchId);
  };

  const handleClose = () => {
    stopPolling();
    if (ranBatch.current) onFinished?.();
    onClose();
  };

  const handleRefresh = () => {
    onFinished?.();
    ranBatch.current = false;
    handleClose();
  };

  if (!open) return null;

  const countNum = parseCount(count);
  const countError = count.trim() !== "" && countNum === null;
  const percentage = progress && progress.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0;
  const orderLabel =
    order === "oldest"
      ? t("applications.autoAnalyzeModal.orderOldest")
      : t("applications.autoAnalyzeModal.orderNewest");
  const filterSummary =
    [company, position].filter(Boolean).join(" · ") || t("applications.autoAnalyzeModal.filterSummaryAll");

  const filterChips = (
    <div className="auto-analyze-chips">
      <span className="chip">{orderLabel}</span>
      <span className="chip chip--info">{filterSummary}</span>
    </div>
  );

  return (
    <Modal open={open} title={t("applications.autoAnalyzeTitle")} onClose={handleClose}>
      {state === "setup" && (
        <form
          className="auto-analyze-setup"
          onSubmit={(event) => {
            event.preventDefault();
            handleStart();
          }}
          noValidate
        >
          <p className="auto-analyze-description">{t("applications.autoAnalyzeModal.eligibleHint")}</p>
          {error && <div className="auto-analyze-error" role="alert">{error}</div>}

          <div className="auto-analyze-grid">
            <Select
              label={t("applications.autoAnalyzeModal.processingOrder")}
              value={order}
              onChange={(value) => setOrder(value as Order)}
              options={[
                { value: "newest", label: t("applications.autoAnalyzeModal.orderNewest") },
                { value: "oldest", label: t("applications.autoAnalyzeModal.orderOldest") },
              ]}
              required
            />
            <TextInput
              label={t("applications.autoAnalyzeModal.numberOfResumes")}
              type="number"
              value={count}
              onChange={setCount}
              required
              hint={t("applications.autoAnalyzeModal.countHint", { max: MAX_BATCH.toLocaleString() })}
              error={countError ? t("applications.autoAnalyzeModal.integerError") : undefined}
            />
          </div>

          <fieldset className="auto-analyze-filters">
            <legend>{t("applications.autoAnalyzeModal.filtersTitle")}</legend>
            <div className="auto-analyze-grid">
              <Select
                label={t("applications.autoAnalyzeModal.company")}
                value={company}
                onChange={(value) => {
                  setCompany(value);
                  setPosition(ALL);
                }}
                options={[
                  { value: ALL, label: t("applications.autoAnalyzeModal.all") },
                  ...companies.map((name) => ({ value: name, label: name })),
                ]}
              />
              <Select
                label={t("applications.autoAnalyzeModal.position")}
                value={position}
                onChange={setPosition}
                options={[
                  { value: ALL, label: t("applications.autoAnalyzeModal.all") },
                  ...positions.map((name) => ({ value: name, label: name })),
                ]}
              />
            </div>
          </fieldset>

          <div className="auto-analyze-summary" aria-live="polite">
            {availableCount === null ? (
              <p className="auto-analyze-info">…</p>
            ) : availableCount === 0 ? (
              <p className="auto-analyze-warning">{t("applications.autoAnalyzeModal.noMatch")}</p>
            ) : (
              <p className="auto-analyze-info">
                <strong>{availableCount.toLocaleString()}</strong>{" "}
                {t("applications.autoAnalyzeModal.newApplicationsAvailable")}.{" "}
                {countNum !== null &&
                  (countNum > availableCount
                    ? t("applications.autoAnalyzeModal.onlyAvailable", {
                        available: availableCount.toLocaleString(),
                      })
                    : t("applications.autoAnalyzeModal.willBeAnalyzed", {
                        count: countNum.toLocaleString(),
                        available: availableCount.toLocaleString(),
                      }))}
              </p>
            )}
          </div>

          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>{t("common.cancel")}</Button>
            <Button
              type="submit"
              loading={starting}
              disabled={countNum === null || !availableCount}
            >
              {t("applications.autoAnalyzeModal.startAnalysis")}
            </Button>
          </div>
        </form>
      )}

      {state === "running" && progress && (
        <div className="auto-analyze-progress">
          <h3 className="auto-analyze-progress-title">
            {t("applications.autoAnalyzeModal.analyzingProgress", {
              processed: progress.processed.toLocaleString(),
              total: progress.total.toLocaleString(),
            })}
          </h3>
          {filterChips}
          <div
            className="progress-bar"
            role="progressbar"
            aria-label={t("applications.autoAnalyzeModal.inProgressTitle")}
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="progress-bar-fill" style={{ width: `${percentage}%` }} />
          </div>
          <div className="auto-analyze-progress-results" aria-live="polite">
            <span>✓ {progress.successful} {t("applications.autoAnalyzeModal.successful")}</span>
            {progress.failed > 0 && (
              <span>⚠ {progress.failed} {t("applications.autoAnalyzeModal.failed")}</span>
            )}
            {progress.skipped > 0 && (
              <span>↷ {progress.skipped} {t("applications.autoAnalyzeModal.skipped")}</span>
            )}
          </div>
          <p className="auto-analyze-current">{t("applications.autoAnalyzeModal.continuesInBackground")}</p>
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleStop}>{t("applications.autoAnalyzeModal.stop")}</Button>
            <Button variant="ghost" onClick={handleClose}>{t("labels.close")}</Button>
          </div>
        </div>
      )}

      {state === "completed" && progress && (
        <div className="auto-analyze-completed">
          <h3 className="auto-analyze-success-title">
            {progress.status === "cancelled"
              ? t("applications.autoAnalyzeModal.cancelledTitle")
              : progress.failed > 0
                ? t("applications.autoAnalyzeModal.completedWithErrors", { count: progress.failed })
                : t("applications.autoAnalyzeModal.successTitle")}
          </h3>
          {filterChips}
          <p className="auto-analyze-success-message">
            {progress.status === "cancelled"
              ? t("applications.autoAnalyzeModal.cancelledMessage", {
                  processed: progress.processed,
                  total: progress.total,
                })
              : progress.failed > 0
                ? t("applications.autoAnalyzeModal.summary", {
                    successful: progress.successful.toLocaleString(),
                    failed: progress.failed.toLocaleString(),
                  })
                : t("applications.autoAnalyzeModal.summaryAllGood", {
                    successful: progress.successful.toLocaleString(),
                  })}
            {progress.skipped > 0 &&
              ` ${t("applications.autoAnalyzeModal.summarySkipped", { skipped: progress.skipped })}`}
          </p>
          <div className="auto-analyze-completed-stats">
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value">{progress.processed}</span>
              <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.processed")}</span>
            </div>
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value success">{progress.successful}</span>
              <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.successful")}</span>
            </div>
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value error">{progress.failed}</span>
              <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.failed")}</span>
            </div>
            {progress.skipped > 0 && (
              <div className="auto-analyze-stat-item">
                <span className="auto-analyze-stat-value">{progress.skipped}</span>
                <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.skipped")}</span>
              </div>
            )}
          </div>
          {remainingAfter > 0 && progress.status !== "cancelled" && (
            <p className="auto-analyze-info">
              {t("applications.autoAnalyzeModal.remainingAfter", { remaining: remainingAfter.toLocaleString() })}
            </p>
          )}
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>{t("labels.close")}</Button>
            <Button onClick={handleRefresh}>{t("applications.autoAnalyzeModal.refreshApplications")}</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
