import type { ReactNode } from "react";
import { FileText } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import type { ApplicantAnswer } from "../../types/candidate";

type ApplicationAnswersProps = {
  answers: ApplicantAnswer[];
  /** Actions for file answers (the uploaded resume), e.g. <ResumeActions variant="row" />. */
  fileAction?: ReactNode;
};

/**
 * The candidate's answers from the public form, as a label/value list.
 * File answers show "file attached" with the CV actions instead of the internal
 * storage path; empty optional answers show a dash.
 */
export default function ApplicationAnswers({ answers, fileAction }: ApplicationAnswersProps) {
  const { t } = useLanguage();

  function renderValue(answer: ApplicantAnswer) {
    const { value } = answer;
    if (answer.type === "file") {
      if (!value) return <span className="table-muted">—</span>;
      return (
        <span className="row-actions inline-file-actions">
          <span className="inline-file">
            <FileText size={14} aria-hidden="true" />
            {t("applications.fileAttached")}
          </span>
          {fileAction}
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
