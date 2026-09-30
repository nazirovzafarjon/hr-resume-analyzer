import { CalendarDays, Clock, ExternalLink, MapPin, Video } from "lucide-react";
import { Link } from "react-router-dom";
import Badge from "../ui/Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import type { CandidateInterview } from "../../types/candidatePortal";
import { portalDate, portalTime } from "./portalFormat";

const STATUS_TONE = { upcoming: "primary", completed: "success", cancelled: "neutral" } as const;

/** An interview as a candidate needs it: when, how long, how to join. */
export default function InterviewItem({
  interview,
  showJob = true,
}: {
  interview: CandidateInterview;
  showJob?: boolean;
}) {
  const { t } = useLanguage();
  return (
    <article className="portal-interview">
      <div>
        {showJob && (
          <>
            <h3>{interview.position}</h3>
            <p className="portal-muted" style={{ margin: 0 }}>
              {interview.company_name}
            </p>
          </>
        )}
        <div className="portal-interview-when">
          <span>
            <CalendarDays size={14} aria-hidden="true" /> {portalDate(interview.scheduled_at)}
          </span>
          <span>
            <Clock size={14} aria-hidden="true" /> {portalTime(interview.scheduled_at)} ·{" "}
            {t("portal.interviews.minutes", { count: interview.duration_minutes })}
          </span>
          <span>
            {interview.is_online ? <Video size={14} aria-hidden="true" /> : <MapPin size={14} aria-hidden="true" />}{" "}
            {interview.is_online ? t("portal.interviews.online") : t("portal.interviews.detailsFromTeam")}
          </span>
        </div>
      </div>
      <div className="portal-form-actions" style={{ alignItems: "center" }}>
        <Badge tone={STATUS_TONE[interview.status]} dot>
          {t(`portal.interviews.status.${interview.status}`)}
        </Badge>
        {interview.meeting_link && (
          <a className="btn btn--primary btn--sm" href={interview.meeting_link} target="_blank" rel="noopener noreferrer">
            <ExternalLink size={14} aria-hidden="true" /> {t("portal.interviews.join")}
          </a>
        )}
        {showJob && (
          <Link className="btn btn--secondary btn--sm" to={`/candidate/applications/${interview.application_id}`}>
            {t("portal.interviews.viewApplication")}
          </Link>
        )}
      </div>
    </article>
  );
}
