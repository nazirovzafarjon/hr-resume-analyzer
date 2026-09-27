import { useState, useEffect, useCallback, useRef } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Select from "../forms/Select";
import TextInput from "../forms/TextInput";
import Card from "../ui/Card";
import { useLanguage } from "../../contexts/LanguageContext";
import type { AutoAnalyzeStartRequest, AutoAnalyzeProgressResponse } from "../../services/workersService";
import { getAutoAnalyzeAvailable, startAutoAnalyze, getAutoAnalyzeProgress, cancelAutoAnalyze } from "../../services/workersService";

type ModalState = "setup" | "confirming" | "running" | "completed";

type Props = {
  open: boolean;
  onClose: () => void;
  jobId?: number;
};

export default function AutoAnalyzeModal({ open, onClose, jobId }: Props) {
  const { t } = useLanguage();
  const [state, setState] = useState<ModalState>("setup");
  const [availableCount, setAvailableCount] = useState<number | null>(null);
  const [order, setOrder] = useState<"oldest" | "newest">("oldest");
  const [count, setCount] = useState<string>("");
  const [batchId, setBatchId] = useState<number | null>(null);
  const [progress, setProgress] = useState<AutoAnalyzeProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentApplication, setCurrentApplication] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const orderOptions = [
    { value: "oldest", label: t("applications.autoAnalyzeModal.orderOldest") },
    { value: "newest", label: t("applications.autoAnalyzeModal.orderNewest") },
  ];

  useEffect(() => {
    if (open) {
      setError(null);
      setState("setup");
      setAvailableCount(null);
      setCount("");
      setBatchId(null);
      setProgress(null);
      setCurrentApplication(null);

      let cancelled = false;
      getAutoAnalyzeAvailable(jobId)
        .then((res) => { if (!cancelled) setAvailableCount(res.count); })
        .catch(() => { if (!cancelled) setError(t("applications.autoAnalyzeModal.loadCountFailed")); });

      return () => { cancelled = true; };
    }
  }, [open, jobId, t]);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  const startPolling = useCallback((id: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const p = await getAutoAnalyzeProgress(id);
        setProgress(p);
        if (p.current_application_id) {
          setCurrentApplication(
            t("applications.autoAnalyzeModal.applicationNumber", { id: p.current_application_id }),
          );
        }
        if (p.status === "completed" || p.status === "cancelled" || p.status === "failed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          if (p.status === "completed" || p.status === "failed") {
            setState("completed");
          }
        }
      } catch { /* ignore */ }
    }, 2000);
  }, [t]);

  const handleStart = async () => {
    const countNum = parseInt(count, 10);
    if (isNaN(countNum) || countNum < 1) {
      setError(t("applications.autoAnalyzeModal.minResumeError"));
      return;
    }
    if (countNum > 1000) {
      setError(t("applications.autoAnalyzeModal.maxResumeError"));
      return;
    }
    if (availableCount === null) return;

    setError(null);
    if (countNum > availableCount) {
      setState("confirming");
      return;
    }

    try {
      const request: AutoAnalyzeStartRequest = { count: countNum, order, job_id: jobId };
      const res = await startAutoAnalyze(request);
      setBatchId(res.batch_id);
      setProgress({
        batch_id: res.batch_id,
        status: res.status,
        total: res.selected_count,
        processed: 0,
        successful: 0,
        failed: 0,
        remaining: res.selected_count,
        current_application_id: null,
        created_at: null,
        finished_at: null,
      });
      setState("running");
      startPolling(res.batch_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("applications.autoAnalyzeModal.startFailed"));
    }
  };

  const handleConfirm = async () => {
    if (availableCount === null) return;
    const countNum = Math.min(parseInt(count, 10), availableCount);
    try {
      const request: AutoAnalyzeStartRequest = { count: countNum, order, job_id: jobId };
      const res = await startAutoAnalyze(request);
      setBatchId(res.batch_id);
      setProgress({
        batch_id: res.batch_id,
        status: res.status,
        total: res.selected_count,
        processed: 0,
        successful: 0,
        failed: 0,
        remaining: res.selected_count,
        current_application_id: null,
        created_at: null,
        finished_at: null,
      });
      setState("running");
      startPolling(res.batch_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("applications.autoAnalyzeModal.startFailed"));
      setState("setup");
    }
  };

  const handleCancel = async () => {
    if (batchId === null) return;
    try {
      await cancelAutoAnalyze(batchId);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      const p = await getAutoAnalyzeProgress(batchId);
      setProgress(p);
      setState("completed");
    } catch { /* ignore */ }
  };

  const handleClose = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    onClose();
  };

  const countNum = parseInt(count, 10);
  const countValid = !isNaN(countNum) && countNum >= 1 && countNum <= 1000;
  const startDisabled = !countValid || availableCount === null || state !== "setup";
  const percentage = progress ? Math.round((progress.processed / progress.total) * 100) : 0;

  const progressBar = (percent: number) => {
    const filled = Math.min(percent, 100);
    const empty = 100 - filled;
    return (
      <div className="progress-bar" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="progress-bar-fill" style={{ width: `${filled}%` }} />
        <div className="progress-bar-empty" style={{ width: `${empty}%` }} />
      </div>
    );
  };

  if (!open) return null;

  return (
    <Modal open={open} title={t("applications.autoAnalyzeTitle")} onClose={handleClose}>
      {state === "setup" && (
        <div className="auto-analyze-setup">
          <p className="auto-analyze-description">{t("applications.autoAnalyzeDescription")}</p>
          {error && <div className="auto-analyze-error" role="alert">{error}</div>}
          <div className="auto-analyze-stat">
            <Card>
              <div className="auto-analyze-count">
                <span className="auto-analyze-count-value">
                  {availableCount !== null ? availableCount.toLocaleString() : "—"}
                </span>
                <span className="auto-analyze-count-label">
                  {t("applications.autoAnalyzeModal.newApplicationsAvailable")}
                </span>
              </div>
            </Card>
          </div>
          <div className="auto-analyze-field">
            <Select
              label={t("applications.autoAnalyzeModal.processingOrder")}
              value={order}
              onChange={(v) => setOrder(v as "oldest" | "newest")}
              options={orderOptions}
            />
          </div>
          <div className="auto-analyze-field">
            <TextInput
              label={t("applications.autoAnalyzeModal.numberOfResumes")}
              type="number"
              value={count}
              onChange={setCount}
              placeholder="50"
              disabled={availableCount === null}
            />
          </div>
          {availableCount !== null && countNum > 0 && (
            <div className="auto-analyze-summary">
              {countNum > availableCount ? (
                <p className="auto-analyze-warning">
                  {t("applications.autoAnalyzeModal.onlyAvailable", { available: availableCount.toLocaleString() })}
                </p>
              ) : (
                <p className="auto-analyze-info">
                  {t("applications.autoAnalyzeModal.willBeAnalyzed", {
                    count: countNum.toLocaleString(),
                    available: availableCount.toLocaleString(),
                  })}
                </p>
              )}
            </div>
          )}
          {count === "0" && (
            <p className="auto-analyze-error">{t("applications.autoAnalyzeModal.minResumeError")}</p>
          )}
          {count && !isNaN(countNum) && countNum > 1000 && (
            <p className="auto-analyze-error">{t("applications.autoAnalyzeModal.maxResumeError")}</p>
          )}
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>{t("common.cancel")}</Button>
            <Button
              variant="primary"
              onClick={handleStart}
              disabled={startDisabled}
              loading={availableCount === null}
            >
              {t("applications.autoAnalyzeModal.startAnalysis")}
            </Button>
          </div>
        </div>
      )}

      {state === "confirming" && availableCount !== null && (
        <div className="auto-analyze-confirm">
          <h3 className="auto-analyze-confirm-title">{t("applications.autoAnalyzeModal.readyToAnalyze")}</h3>
          <div className="auto-analyze-confirm-stats">
            <p>
              <strong>{availableCount.toLocaleString()}</strong>{" "}
              {t("applications.autoAnalyzeModal.newApplicationsLabel")}
            </p>
            <p>
              {t("applications.autoAnalyzeModal.orderLabel")}{" "}
              <strong>
                {order === "oldest"
                  ? t("applications.autoAnalyzeModal.orderOldest")
                  : t("applications.autoAnalyzeModal.orderNewest")}
              </strong>
            </p>
          </div>
          <p className="auto-analyze-confirm-note">{t("applications.autoAnalyzeModal.confirmNote")}</p>
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={() => setState("setup")}>{t("common.cancel")}</Button>
            <Button variant="primary" onClick={handleConfirm}>
              {t("applications.autoAnalyzeModal.startAnalysis")}
            </Button>
          </div>
        </div>
      )}

      {state === "running" && progress && (
        <div className="auto-analyze-progress">
          <h3 className="auto-analyze-progress-title">{t("applications.autoAnalyzeModal.inProgressTitle")}</h3>
          {progressBar(percentage)}
          <div className="auto-analyze-progress-stats">
            <p>
              <strong>{progress.processed}</strong>{" "}
              {t("applications.autoAnalyzeModal.analyzedOfTotal", { total: progress.total })}
            </p>
            <div className="auto-analyze-progress-results">
              <span>✓ {progress.successful} {t("applications.autoAnalyzeModal.successful")}</span>
              {progress.failed > 0 && (
                <span>⚠ {progress.failed} {t("applications.autoAnalyzeModal.failed")}</span>
              )}
            </div>
          </div>
          {currentApplication && (
            <p className="auto-analyze-current">
              {t("applications.autoAnalyzeModal.currentlyAnalyzing", { name: currentApplication })}
            </p>
          )}
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleCancel}>{t("common.cancel")}</Button>
            <Button variant="ghost" onClick={handleClose}>
              {t("applications.autoAnalyzeModal.viewApplications")}
            </Button>
          </div>
        </div>
      )}

      {state === "completed" && progress && (
        <div className="auto-analyze-completed">
          {progress.failed === 0 ? (
            <>
              <h3 className="auto-analyze-success-title">
                {t("applications.autoAnalyzeModal.successTitle")}
              </h3>
              <p className="auto-analyze-success-message">
                {t("applications.autoAnalyzeModal.successMessage", { count: progress.total.toLocaleString() })}
              </p>
            </>
          ) : (
            <>
              <h3 className="auto-analyze-success-title">
                {t("applications.autoAnalyzeModal.completedWithErrors", { count: progress.failed })}
              </h3>
              <p className="auto-analyze-success-message">
                {t("applications.autoAnalyzeModal.partialSuccessMessage", {
                  successful: progress.successful.toLocaleString(),
                  failed: progress.failed.toLocaleString(),
                })}
              </p>
            </>
          )}
          <div className="auto-analyze-completed-stats">
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value">{progress.total}</span>
              <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.processed")}</span>
            </div>
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value success">{progress.successful}</span>
              <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.successful")}</span>
            </div>
            {progress.failed > 0 && (
              <div className="auto-analyze-stat-item">
                <span className="auto-analyze-stat-value error">{progress.failed}</span>
                <span className="auto-analyze-stat-label">{t("applications.autoAnalyzeModal.failed")}</span>
              </div>
            )}
          </div>
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>{t("labels.close")}</Button>
            <Button variant="primary" onClick={() => window.location.href = "/applications"}>
              {t("applications.autoAnalyzeModal.viewApplications")}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
