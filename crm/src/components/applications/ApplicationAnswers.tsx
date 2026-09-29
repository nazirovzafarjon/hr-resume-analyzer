import { FileText } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import type { ApplicantAnswer } from "../../types/worker";

type ApplicationAnswersProps = {
  answers: ApplicantAnswer[];
  /** Link for file answers (the uploaded resume), when the backend provides one. */
  fileUrl?: string | null;
};

/**
 * The candidate's answers from the public form, as a label/value list.
 * File answers show "file attached" with an open link instead of the internal
 * storage path; empty optional answers show a dash.
 */
export default function ApplicationAnswers({ answers, fileUrl }: ApplicationAnswersProps) {
  const { t } = useLanguage();

  function renderValue(answer: ApplicantAnswer) {
    const { value } = answer;
    if (answer.type === "file") {
      if (!value) return <span className="table-muted">—</span>;
      return fileUrl ? (
        <a className="link inline-file" href={fileUrl} target="_blank" rel="noopener noreferrer">
          <FileText size={14} aria-hidden="true" />
          {t("applications.fileAttached")}
        </a>
      ) : (
        <span className="inline-file">
          <FileText size={14} aria-hidden="true" />
          {t("applications.fileAttached")}
        </span>
      );
    }
    if (typeof value === "boolean") return value ? t("common.yes") : t("common.no");
    if (Array.isArray(value)) return value.length ? value.join(", ") : <span className="table-muted">—</span>;
    if (value === null || value === undefined || String(value).trim() === "") {
      return <span className="table-muted">—</span>;
    }
    return String(value);
  }

  return (
    <dl className="detail-list">
      {answers.map((answer, index) => (
        <div key={answer.field_id || index} className="detail-list-row">
          <dt>{answer.label || answer.key}</dt>
          <dd>{renderValue(answer)}</dd>
        </div>
      ))}
    </dl>
  );
}
