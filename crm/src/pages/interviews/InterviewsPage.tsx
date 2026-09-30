import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Video } from "lucide-react";
import { formatDateTime } from "../../utils/date";
import { getErrorMessage } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import FilterBar from "../../components/ui/FilterBar";
import ErrorState from "../../components/ui/ErrorState";
import Table from "../../components/ui/Table";
import Modal from "../../components/ui/Modal";
import Select from "../../components/forms/Select";
import FormField from "../../components/forms/FormField";
import TextInput from "../../components/forms/TextInput";
import TextArea from "../../components/forms/TextArea";
import StatCard from "../../components/ui/StatCard";
import InterviewStatusBadge from "../../components/ui/InterviewStatusBadge";
import { SkeletonCards } from "../../components/ui/Skeleton";
import {
  createInterview,
  fetchInterviews,
  fetchInterviewStats,
  toUtcIso,
  type InterviewStats,
} from "../../services/interviewsService";
import { fetchCandidates } from "../../services/workersService";
import { fetchJobs } from "../../services/jobsService";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import type { Candidate } from "../../types/worker";
import type { JobInput } from "../../types/job";
import type { Interview, InterviewStatusFilter } from "../../types/application";

const EMPTY_STATS: InterviewStats = {
  total: 0,
  upcoming: 0,
  completed: 0,
  cancelled: 0,
};

/** /interviews — API-driven interview schedule with live search and filters. */
export default function InterviewsPage() {
  const { t } = useLanguage();
  const notify = useNotify();

  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [stats, setStats] = useState<InterviewStats>(EMPTY_STATS);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<JobInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<InterviewStatusFilter | "all">("all");
  const [search, setSearch] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [candidateId, setCandidateId] = useState("");
  const [interviewer, setInterviewer] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [duration, setDuration] = useState("60");
  const [meetingLink, setMeetingLink] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const filters: { value: InterviewStatusFilter | "all"; label: string }[] = [
    { value: "all", label: t("interviews.filters.all") || "All interviews" },
    { value: "upcoming", label: t("interviews.filters.upcoming") || "Upcoming" },
    { value: "completed", label: t("interviews.filters.completed") || "Completed" },
    { value: "cancelled", label: t("interviews.filters.cancelled") || "Cancelled" },
  ];

  async function refreshList(statusValue: InterviewStatusFilter | "all", query: string) {
    try {
      const data = await fetchInterviews({
        status: statusValue === "all" ? undefined : statusValue,
        search: query.trim() ? query.trim() : undefined,
      });
      setInterviews(data);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function refreshStats() {
    try {
      setStats(await fetchInterviewStats());
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  // Initial load
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [candidateList, jobList, interviewList, interviewStats] = await Promise.all([
          fetchCandidates(),
          fetchJobs(),
          fetchInterviews(),
          fetchInterviewStats(),
        ]);
        if (cancelled) return;
        setCandidates(candidateList);
        setJobs(jobList);
        setInterviews(interviewList);
        setStats(interviewStats);
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Live search (debounced) + status filter
  useEffect(() => {
    if (loading) return;
    const timer = setTimeout(() => {
      void refreshList(filter, search);
    }, 300);
    return () => clearTimeout(timer);
  }, [filter, search, loading]);

  function resetForm() {
    setCandidateId("");
    setInterviewer("");
    setScheduledAt("");
    setDuration("60");
    setMeetingLink("");
    setNotes("");
    setFormError(null);
  }

  async function handleCreate() {
    if (!candidateId) {
      setFormError("Please select a candidate.");
      return;
    }
    if (!interviewer.trim()) {
      setFormError("Please enter the interviewer name.");
      return;
    }
    if (!scheduledAt) {
      setFormError("Please pick a date and time.");
      return;
    }
    const durationMinutes = Number(duration);
    if (!Number.isInteger(durationMinutes) || durationMinutes < 5 || durationMinutes > 480) {
      setFormError("Duration must be between 5 and 480 minutes.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await createInterview({
        candidate_id: Number(candidateId),
        interviewer: interviewer.trim(),
        scheduled_at: toUtcIso(scheduledAt),
        duration_minutes: durationMinutes,
        meeting_link: meetingLink.trim() ? meetingLink.trim() : null,
        notes: notes.trim() ? notes.trim() : null,
      });
      setModalOpen(false);
      resetForm();
      notify.success(t("toast.statusUpdated") || "Interview scheduled successfully");
      await Promise.all([refreshList(filter, search), refreshStats()]);
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function jobById(id: number): JobInput | undefined {
    return jobs.find((job) => job.id === id);
  }

  if (loading) {
    return (
      <div className="page">
        <PageHeader
          title={t("interviews.title") || "Interviews"}
          description={t("interviews.description") || "Schedule and track manual HR interviews for your candidates."}
          action={
            <Button icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>
              {t("interviews.createInterview") || "Schedule Interview"}
            </Button>
          }
        />
        <SkeletonCards count={4} />
      </div>
    );
  }

  if (error && interviews.length === 0) {
    return (
      <div className="page">
        <PageHeader
          title={t("interviews.title") || "Interviews"}
          description={t("interviews.description") || "Schedule and track manual HR interviews for your candidates."}
        />
        <ErrorState
          message={error}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setLoading(true);
                setError(null);
                Promise.all([refreshList(filter, search), refreshStats()]).finally(() =>
                  setLoading(false),
                );
              }}
            >
              {t("common.retry") || "Retry"}
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="page">
      <PageMeta title={t("nav.interviews")} noindex />
      <PageHeader
        title={t("interviews.title") || "Interviews"}
        description={t("interviews.description") || "Schedule and track manual HR interviews for your candidates."}
        action={
          <Button icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>
            {t("interviews.createInterview") || "Schedule Interview"}
          </Button>
        }
      />

      <div className="stat-grid">
        <StatCard label={t("stats.total") || "Total interviews"} value={stats.total} hint={t("stats.totalHint") || "all time"} />
        <StatCard label={t("stats.upcoming") || "Upcoming"} value={stats.upcoming} hint={t("stats.upcomingHint") || "scheduled"} tone="info" />
        <StatCard label={t("stats.completed") || "Completed"} value={stats.completed} hint={t("stats.completedHint") || "finished"} tone="success" />
        <StatCard label={t("stats.cancelled") || "Cancelled"} value={stats.cancelled} hint={t("stats.cancelledHint") || "cancelled"} tone="danger" />
      </div>

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("interviews.searchPlaceholder") }}
          active={search.trim() !== "" || filter !== "all"}
          onClear={() => {
            setSearch("");
            setFilter("all");
          }}
        >
          <label className="toolbar-label">
            {t("labels.status") || "Status"}
            <select
              className="field-select"
              value={filter}
              onChange={(event) => setFilter(event.target.value as InterviewStatusFilter | "all")}
            >
              {filters.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </FilterBar>

        {interviews.length === 0 ? (
          <EmptyState
            title={t("empty.interviewsTitle") || "No interviews found"}
            message={
              search.trim() || filter !== "all"
                ? (t("empty.noMatchingMessage") || "Try adjusting your search or filters.")
                : (t("empty.interviewsMessage") || "Schedule your first interview to start tracking candidate meetings.")
            }
            action={
              search.trim() || filter !== "all" ? undefined : (
                <Button icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>
                  {t("interviews.createInterview") || "Schedule Interview"}
                </Button>
              )
            }
          />
        ) : (
          <Table
            pageSize={20}
            rows={interviews}
            rowKey={(interview) => interview.id}
            columns={[
              {
                header: t("interviews.candidate") || "Candidate",
                render: (interview) => (
                  <div>
                    <Link className="table-primary" to={`/interviews/${interview.id}`}>
                      {interview.candidate_name}
                    </Link>
                    <div className="table-secondary">
                      {interview.job_title} · {interview.company_name}
                    </div>
                  </div>
                ),
              },
              {
                header: t("interviews.scheduled") || "Scheduled",
                render: (interview) => (
                  <div>
                    <div className="table-primary">{formatDateTime(interview.scheduled_at)}</div>
                    <div className="table-secondary">{t("common.minutes", { count: interview.duration_minutes })}</div>
                  </div>
                ),
              },
              { header: t("interviews.interviewer") || "Interviewer", render: (interview) => interview.interviewer },
              {
                header: t("labels.status") || "Status",
                render: (interview) => <InterviewStatusBadge value={interview.status} />,
              },
              {
                header: t("interviews.meeting"),
                render: (interview) =>
                  interview.meeting_link ? (
                    <a
                      className="link"
                      href={interview.meeting_link}
                      target="_blank"
                      rel="noreferrer"
                      style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
                    >
                      <Video size={14} /> Join
                    </a>
                  ) : (
                    "—"
                  ),
              },
              {
                header: t("labels.actions") || "Actions",
                hideOnMobile: true,
                headerClassName: "table-actions-cell",
                className: "table-actions-cell",
                render: (interview) => (
                  <Link className="row-action" to={`/interviews/${interview.id}`}>
                    {t("common.view") || "View"}
                  </Link>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Modal
        open={modalOpen}
        title={t("interviews.createInterview") || "Schedule Interview"}
        onClose={() => {
          if (!submitting) {
            setModalOpen(false);
            resetForm();
          }
        }}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setModalOpen(false);
                resetForm();
              }}
              disabled={submitting}
            >
              {t("common.cancel") || "Cancel"}
            </Button>
            <Button onClick={handleCreate} loading={submitting}>
              {t("interviews.schedule") || "Schedule interview"}
            </Button>
          </>
        }
      >
        <Select
          label={t("interviews.candidate") || "Candidate"}
          value={candidateId}
          onChange={setCandidateId}
          required
          options={[
            { value: "", label: candidates.length === 0 ? t("interviews.noCandidatesOption") : t("interviews.selectCandidate") },
            ...candidates.map((candidate) => {
              const job = jobById(candidate.job_id);
              return {
                value: String(candidate.id),
                label: job
                  ? `${candidate.name} — ${job.position} @ ${job.company_name}`
                  : candidate.name,
              };
            }),
          ]}
        />
        <TextInput
          label={t("interviews.interviewer") || "Interviewer"}
          value={interviewer}
          onChange={setInterviewer}
          required
          placeholder="e.g. Anna HR"
        />
        <FormField label={t("interviews.scheduled") || "Scheduled at"} required hint="Local time; stored as UTC.">
          {(id) => (
            <input
              id={id}
              className="field-input"
              type="datetime-local"
              value={scheduledAt}
              onChange={(event) => setScheduledAt(event.target.value)}
            />
          )}
        </FormField>
        <FormField label={`${t("interviews.duration") || "Duration"} (minutes)`} required>
          {(id) => (
            <input
              id={id}
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
          hint="Zoom, Google Meet, or Microsoft Teams link."
        >
          {(id) => (
            <input
              id={id}
              className="field-input"
              type="url"
              value={meetingLink}
              onChange={(event) => setMeetingLink(event.target.value)}
              placeholder="https://meet.example.com/round-1"
            />
          )}
        </FormField>
        <TextArea
          label="Notes"
          value={notes}
          onChange={setNotes}
          placeholder="Agenda, round, topics to cover…"
        />
        {formError && (
          <p className="field-error" role="alert">
            {formError}
          </p>
        )}
      </Modal>
    </div>
  );
}
