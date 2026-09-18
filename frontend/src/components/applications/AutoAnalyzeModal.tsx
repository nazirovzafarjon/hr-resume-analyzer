import { useState, useEffect, useCallback, useRef } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Select from "../forms/Select";
import TextInput from "../forms/TextInput";
import Card from "../ui/Card";
import type { AutoAnalyzeStartRequest, AutoAnalyzeProgressResponse } from "../../services/workersService";
import { getAutoAnalyzeAvailable, startAutoAnalyze, getAutoAnalyzeProgress, cancelAutoAnalyze } from "../../services/workersService";

type ModalState = "setup" | "confirming" | "running" | "completed";

type Props = {
  open: boolean;
  onClose: () => void;
  jobId?: number;
};

const ORDER_OPTIONS = [
  { value: "oldest", label: "Oldest first" },
  { value: "newest", label: "Newest first" },
];

export default function AutoAnalyzeModal({ open, onClose, jobId }: Props) {
  const [state, setState] = useState<ModalState>("setup");
  const [availableCount, setAvailableCount] = useState<number | null>(null);
  const [order, setOrder] = useState<"oldest" | "newest">("oldest");
  const [count, setCount] = useState<string>("");
  const [batchId, setBatchId] = useState<number | null>(null);
  const [progress, setProgress] = useState<AutoAnalyzeProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentApplication, setCurrentApplication] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

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
        .catch(() => { if (!cancelled) setError("Failed to load available count"); });

      return () => { cancelled = true; };
    }
  }, [open, jobId]);

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
          setCurrentApplication(`Application #${p.current_application_id}`);
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
  }, []);

  const handleStart = async () => {
    const countNum = parseInt(count, 10);
    if (isNaN(countNum) || countNum < 1) {
      setError("Enter at least 1 resume.");
      return;
    }
    if (countNum > 1000) {
      setError("Maximum is 1,000 resumes per batch.");
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
      setError(err instanceof Error ? err.message : "Failed to start analysis");
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
      setError(err instanceof Error ? err.message : "Failed to start analysis");
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
    <Modal open={open} title="Auto Analyze Applications" onClose={handleClose}>
      {state === "setup" && (
        <div className="auto-analyze-setup">
          <p className="auto-analyze-description">
            Analyze new resumes automatically against their job requirements.
          </p>
          {error && <div className="auto-analyze-error" role="alert">{error}</div>}
          <div className="auto-analyze-stat">
            <Card>
              <div className="auto-analyze-count">
                <span className="auto-analyze-count-value">
                  {availableCount !== null ? availableCount.toLocaleString() : "—"}
                </span>
                <span className="auto-analyze-count-label">New applications available</span>
              </div>
            </Card>
          </div>
          <div className="auto-analyze-field">
            <Select
              label="Processing order"
              value={order}
              onChange={(v) => setOrder(v as "oldest" | "newest")}
              options={ORDER_OPTIONS}
            />
          </div>
          <div className="auto-analyze-field">
            <TextInput
              label="Number of resumes"
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
                  Only {availableCount.toLocaleString()} new applications are available.
                  We&apos;ll analyze all {availableCount.toLocaleString()}.
                </p>
              ) : (
                <p className="auto-analyze-info">
                  {countNum.toLocaleString()} of {availableCount.toLocaleString()} available
                  resumes will be analyzed.
                </p>
              )}
            </div>
          )}
          {count === "0" && <p className="auto-analyze-error">Enter at least 1 resume.</p>}
          {count && !isNaN(countNum) && countNum > 1000 && (
            <p className="auto-analyze-error">Maximum is 1,000 resumes per batch.</p>
          )}
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>Cancel</Button>
            <Button
              variant="primary"
              onClick={handleStart}
              disabled={startDisabled}
              loading={availableCount === null}
            >
              Start Analysis
            </Button>
          </div>
        </div>
      )}

      {state === "confirming" && availableCount !== null && (
        <div className="auto-analyze-confirm">
          <h3 className="auto-analyze-confirm-title">Ready to analyze</h3>
          <div className="auto-analyze-confirm-stats">
            <p><strong>{availableCount.toLocaleString()}</strong> new applications</p>
            <p>Order: <strong>{order === "oldest" ? "Oldest first" : "Newest first"}</strong></p>
          </div>
          <p className="auto-analyze-confirm-note">
            The resumes will be analyzed one by one against their job requirements.
            You can continue working while analysis runs.
          </p>
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={() => setState("setup")}>Cancel</Button>
            <Button variant="primary" onClick={handleConfirm}>Start Analysis</Button>
          </div>
        </div>
      )}

      {state === "running" && progress && (
        <div className="auto-analyze-progress">
          <h3 className="auto-analyze-progress-title">AI analysis in progress</h3>
          {progressBar(percentage)}
          <div className="auto-analyze-progress-stats">
            <p><strong>{progress.processed}</strong> of {progress.total} analyzed</p>
            <div className="auto-analyze-progress-results">
              <span>✓ {progress.successful} successful</span>
              {progress.failed > 0 && <span>⚠ {progress.failed} failed</span>}
            </div>
          </div>
          {currentApplication && (
            <p className="auto-analyze-current">Currently analyzing: {currentApplication}</p>
          )}
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleCancel}>Cancel</Button>
            <Button variant="ghost" onClick={handleClose}>View Applications</Button>
          </div>
        </div>
      )}

      {state === "completed" && progress && (
        <div className="auto-analyze-completed">
          {progress.failed === 0 ? (
            <>
              <h3 className="auto-analyze-success-title">Analysis complete 🎉</h3>
              <p className="auto-analyze-success-message">
                {progress.total.toLocaleString()} resumes have been analyzed successfully.
              </p>
            </>
          ) : (
            <>
              <h3 className="auto-analyze-success-title">
                Analysis completed with {progress.failed} error{progress.failed !== 1 ? "s" : ""}
              </h3>
              <p className="auto-analyze-success-message">
                {progress.successful.toLocaleString()} resumes analyzed successfully.
                {progress.failed > 0 && (
                  <> {progress.failed.toLocaleString()} resumes could not be analyzed.</>
                )}
              </p>
            </>
          )}
          <div className="auto-analyze-completed-stats">
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value">{progress.total}</span>
              <span className="auto-analyze-stat-label">Processed</span>
            </div>
            <div className="auto-analyze-stat-item">
              <span className="auto-analyze-stat-value success">{progress.successful}</span>
              <span className="auto-analyze-stat-label">Successful</span>
            </div>
            {progress.failed > 0 && (
              <div className="auto-analyze-stat-item">
                <span className="auto-analyze-stat-value error">{progress.failed}</span>
                <span className="auto-analyze-stat-label">Failed</span>
              </div>
            )}
          </div>
          <div className="auto-analyze-actions">
            <Button variant="secondary" onClick={handleClose}>Close</Button>
            <Button variant="primary" onClick={() => window.location.href = "/applications"}>
              View Applications
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}