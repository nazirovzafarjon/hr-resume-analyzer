import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Video, Edit3, Trash2 } from "lucide-react";
import { formatDateTime } from "../../utils/date";
import { getErrorMessage } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import Modal from "../../components/ui/Modal";
import Select from "../../components/forms/Select";
import FormField from "../../components/forms/FormField";
import TextInput from "../../components/forms/TextInput";
import TextArea from "../../components/forms/TextArea";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import InterviewStatusBadge from "../../components/ui/InterviewStatusBadge";
import {
  deleteInterview,
  fetchInterview,
  toLocalInputValue,
  toUtcIso,
  updateInterview,
} from "../../services/interviewsService";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import type { Interview, InterviewStatusFilter } from "../../types/application";

/** /interviews/:id - single manual HR interview loaded from the backend API. */
export default function InterviewDetailsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const params = useParams();
  const navigate = useNavigate();
  const id = Number(params.id);

  const [interview, setInterview] = useState<Interview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [interviewer, setInterviewer] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [duration, setDuration] = useState("60");
  const [meetingLink, setMeetingLink] = useState("");
  const [notes, setNotes] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [statusValue, setStatusValue] = useState<InterviewStatusFilter>("upcoming");
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const statusOptions: { value: InterviewStatusFilter; label: string }[] = [
    { value: "upcoming", label: t("interviews.filters.upcoming") || "Upcoming" },
    { value: "completed", label: t("interviews.filters.completed") || "Completed" },
    { value: "cancelled", label: t("interviews.filters.cancelled") || "Cancelled" },
  ];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchInterview(id);
        if (cancelled) return;
        setInterview(data);
        setStatusValue(data.status);
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  function openEdit() {
    if (!interview) return;
    setInterviewer(interview.interviewer);
    setScheduledAt(toLocalInputValue(interview.scheduled_at));
    setDuration(String(interview.duration_minutes));
    setMeetingLink(interview.meeting_link ?? "");
    setNotes(interview.notes ?? "");
    setEditError(null);
    setEditOpen(true);
  }

  async function handleSaveEdit() {
    if (!interview) return;
    if (!interviewer.trim()) {
      setEditError("Please enter the interviewer name.");
      return;
    }
    if (!scheduledAt) {
      setEditError("Please pick a date and time.");
      return;
    }
    const durationMinutes = Number(duration);
    if (!Number.isInteger(durationMinutes) || durationMinutes < 5 || durationMinutes > 480) {
      setEditError("Duration must be between 5 and 480 minutes.");
      return;
    }
    setSaving(true);
    setEditError(null);
    try {
      const updated = await updateInterview(interview.id, {
        interviewer: interviewer.trim(),
        scheduled_at: toUtcIso(scheduledAt),
        duration_minutes: durationMinutes,
        meeting_link: meetingLink.trim() ? meetingLink.trim() : null,
        notes: notes.trim() ? notes.trim() : null,
      });
      setInterview(updated);
      setEditOpen(false);
      notify.success(t("toast.jobUpdated") || "Interview updated successfully");
    } catch (err) {
      setEditError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(next: InterviewStatusFilter) {
    if (!interview) return;
    if (next === interview.status) {
      setStatusValue(next);
      return;
    }
    setStatusSaving(true);
    setStatusError(null);
    try {
      const updated = await updateInterview(interview.id, { status: next });
      setInterview(updated);
      setStatusValue(updated.status);
      notify.success(t("toast.statusUpdated") || "Status updated");
    } catch (err) {
      setStatusError(getErrorMessage(err));
      setStatusValue(interview.status);
    } finally {
      setStatusSaving(false);
    }
  }

  async function handleDelete() {
    if (!interview) return;
    setDeleting(true);
    try {
      await deleteInterview(interview.id);
      notify.success(t("toast.jobDeleted") || "Interview deleted");
      navigate("/interviews");
    } catch (err) {
      setStatusError(getErrorMessage(err));
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("pages.interviewDetails") || "Interview"} description={t("common.loading") || "Loading interview details."} />
        <Card>
          <div className="loading-state">{t("common.loading") || "Loading interview…"}</div>
        </Card>
      </div>
    );
  }

  if (error || !interview) {
    return (
      <div className="page">
        <PageHeader title={t("labels.notFoundTitle") || "Interview not found"} description={t("errors.notFoundMessage") || "This interview may have been removed."} />
        <Card>
          <EmptyState
            tone="error"
            title={t("labels.notFoundTitle") || "Interview not found"}
            message={error ?? (t("errors.notFoundMessage") || "The interview you are looking for may have been deleted.")}
            action={
              <Button to="/interviews" icon={<ArrowLeft size={16} />}>
                {t("common.back") || "Back to interviews"}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title={interview.candidate_name}
        description={`${interview.job_title} at ${interview.company_name}`}
        action={
          <Button variant="secondary" to="/interviews" icon={<ArrowLeft size={16} />}>
            {t("common.back") || "Back"}
          </Button>
        }
      />
      <div className="job-summary-grid">
        <Card title={t("interviews.scheduled") || "Schedule"} subtitle="When and where this interview takes place.">
          <dl className="detail-list">
            <dt>{t("interviews.scheduled") || "Scheduled at"}</dt>
            <dd>{formatDateTime(interview.scheduled_at)}</dd>
            <dt>{t("interviews.duration") || "Duration"}</dt>
            <dd>{interview.duration_minutes} minutes</dd>
            <dt>{t("interviews.interviewer") || "Interviewer"}</dt>
            <dd>{interview.interviewer}</dd>
            <dt>Meeting link</dt>
            <dd>
              {interview.meeting_link ? (
                <a className="link" href={interview.meeting_link} target="_blank" rel="noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  <Video size={14} /> {interview.meeting_link}
                </a>
              ) : (
                "—"
              )}
            </dd>
          </dl>
          <div className="job-form-actions">
            <Button variant="secondary" onClick={openEdit} icon={<Edit3 size={15} />}>
              {t("common.edit") || "Edit / Reschedule"}
            </Button>
          </div>
        </Card>

        <Card title={`${t("labels.status") || "Status"} & Notes`} subtitle="Track the outcome of this interview.">
          <div className="chip-row">
            <InterviewStatusBadge value={interview.status} />
          </div>
          <Select
            label={t("labels.status") || "Change status"}
            value={statusValue}
            onChange={(value) => {
              const next = value as InterviewStatusFilter;
              setStatusValue(next);
              void handleStatusChange(next);
            }}
            options={statusOptions}
            disabled={statusSaving}
          />
          {statusError && <ErrorState message={statusError} />}
          <dl className="detail-list">
            <dt>{t("interviews.candidate") || "Candidate"}</dt>
            <dd>{interview.candidate_name}</dd>
            <dt>Notes</dt>
            <dd>{interview.notes && interview.notes.trim() ? interview.notes : "No notes yet"}</dd>
          </dl>
          <div className="job-form-actions">
            <Button variant="danger" onClick={() => setConfirmDelete(true)} icon={<Trash2 size={15} />}>
              {t("common.delete") || "Delete"}
            </Button>
          </div>
        </Card>
      </div>

      <Modal
        open={editOpen}
        title={t("common.edit") || "Edit interview"}
        onClose={() => {
          if (!saving) setEditOpen(false);
        }}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditOpen(false)} disabled={saving}>
              {t("common.cancel") || "Cancel"}
            </Button>
            <Button onClick={handleSaveEdit} loading={saving}>
              {t("common.save") || "Save changes"}
            </Button>
          </>
        }
      >
        <TextInput
          label={t("interviews.interviewer") || "Interviewer"}
          value={interviewer}
          onChange={setInterviewer}
          required
          placeholder="e.g. Anna HR"
        />
        <FormField label={t("interviews.scheduled") || "Scheduled at"} required hint="Local time; stored as UTC.">
          {(fieldId) => (
            <input
              id={fieldId}
              className="field-input"
              type="datetime-local"
              value={scheduledAt}
              onChange={(event) => setScheduledAt(event.target.value)}
            />
          )}
        </FormField>
        <FormField label={`${t("interviews.duration") || "Duration"} (minutes)`} required>
          {(fieldId) => (
            <input
              id={fieldId}
              className="field-input"
              type="number"
              min={5}
              max={480}
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />
          )}
        </FormField>
        <FormField
          label="Meeting link"
          hint="Create the meeting in Zoom or Google Meet, then paste the link here."
        >
          {(fieldId) => (
            <input
              id={fieldId}
              className="field-input"
              type="url"
              value={meetingLink}
              onChange={(event) => setMeetingLink(event.target.value)}
              placeholder="https://meet.example.com/round-1"
            />
          )}
        </FormField>
        <TextArea label="Notes" value={notes} onChange={setNotes} placeholder="Agenda, round, topics" />
        {editError && (
          <p className="field-error" role="alert">
            {editError}
          </p>
        )}
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title={t("common.delete") || "Delete this interview?"}
        message={`This will permanently remove the interview with ${interview.candidate_name}.`}
        confirmLabel={t("common.delete") || "Delete"}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
