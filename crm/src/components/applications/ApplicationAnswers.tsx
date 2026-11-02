import type { ReactNode } from "react";
import { FileText } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import type { ApplicantAnswer } from "../../types/candidate";

type ApplicationAnswersProps = {
  answers: ApplicantAnswer[];
  /** Actions for file answers (the uploaded resume), e.g. <ResumeActions variant="row" />. */
  fileAction?: ReactNode;
};

const SYSTEM_FIELD_KEY_MAP: Record<string, string> = {
  full_name: "common.full_name",
  name: "common.full_name",
  "full name": "common.full_name",
  "candidate name": "common.full_name",
  email: "common.email",
  "email address": "common.email",
  phone: "common.phone",
  "phone number": "common.phone",
  resume: "common.resume",
  cv: "common.resume",
  "resume / cv": "common.resume",
  "resume file": "common.resume",
  years_of_experience: "common.years_of_experience",
  "years of experience": "common.years_of_experience",
  experience: "common.years_of_experience",
  portfolio_or_linkedin_url: "common.portfolio_url",
  "portfolio or linkedin url": "common.portfolio_url",
  portfolio: "common.portfolio_url",
  linkedin: "common.portfolio_url",
  cover_letter: "common.cover_letter",
  "cover letter": "common.cover_letter",
  location: "common.location",
  salary_expectations: "common.salary_expectations",
  "salary expectations": "common.salary_expectations",
  notice_period: "common.notice_period",
  "notice period": "common.notice_period",
};

/**
 * The candidate's answers from the public form, as a label/value list.
 * File answers show "file attached" with the CV actions instead of the internal
 * storage path; empty optional answers show a dash.
 */
export default function ApplicationAnswers({ answers, fileAction }: ApplicationAnswersProps) {
  const { t } = useLanguage();

  function getFieldLabel(answer: ApplicantAnswer): string {
    const rawKey = (answer.key || "").trim().toLowerCase();
    const rawLabel = (answer.label || "").trim().toLowerCase();
    const slugKey = rawKey.replace(/[-_]/g, " ");

    const translationKey =
      SYSTEM_FIELD_KEY_MAP[rawKey] ||
      SYSTEM_FIELD_KEY_MAP[slugKey] ||
      SYSTEM_FIELD_KEY_MAP[rawLabel];

    if (translationKey) {
      const translated = t(translationKey);
      if (translated && translated !== translationKey) {
        return translated;
      }
    }

    return answer.label || answer.key;
  }

  function formatAnswer(val: unknown): ReactNode {
    if (typeof val === "boolean") {
      return val ? t("common.yes") : t("common.no");
    }
    if (val === null || val === undefined || String(val).trim() === "") {
      return <span className="table-muted">—</span>;
    }
    if (typeof val === "string") {
      const lower = val.trim().toLowerCase();
      if (["yes", "true", "ha", "да", "ҳа"].includes(lower)) {
        return t("common.yes");
      }
      if (["no", "false", "yo'q", "yo‘q", "нет", "йўқ"].includes(lower)) {
        return t("common.no");
      }
      return val;
    }
    if (Array.isArray(val)) {
      if (!val.length) return <span className="table-muted">—</span>;
      return val
        .map((item) => {
          if (typeof item === "string") {
            const lower = item.trim().toLowerCase();
            if (["yes", "true", "ha", "да", "ҳа"].includes(lower)) return t("common.yes");
            if (["no", "false", "yo'q", "yo‘q", "нет", "йўқ"].includes(lower)) return t("common.no");
          }
          return String(item);
        })
        .join(", ");
    }
    return String(val);
  }

  function renderValue(answer: ApplicantAnswer) {
    if (answer.type === "file") {
      if (!answer.value) return <span className="table-muted">—</span>;
      return (
        <span className="row-actions inline-file-actions">
          <span className="inline-file">
            <FileText size={14} aria-hidden="true" />
            {t("common.file_attached") || t("applications.fileAttached")}
          </span>
          {fileAction}
        </span>
      );
    }
    return formatAnswer(answer.value);
  }

  return (
    <dl className="detail-list">
      {answers.map((answer, index) => (
        <div key={answer.field_id || index} className="detail-list-row">
          <dt>{getFieldLabel(answer)}</dt>
          <dd>{renderValue(answer)}</dd>
        </div>
      ))}
    </dl>
  );
}

