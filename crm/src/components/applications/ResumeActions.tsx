import { Download, Eye } from "lucide-react";
import Button from "../ui/Button";
import { useLanguage } from "../../contexts/LanguageContext";
import { useResumeFile } from "../../hooks/useResumeFile";

type ResumeActionsProps = {
  workerId: number;
  candidateName: string;
  resumePath: string;
  /** "row" renders compact table actions; "card" regular buttons. */
  variant?: "card" | "row";
};

/**
 * "View CV" / "Download CV" for one application. View is offered for formats
 * a browser can display (PDF, TXT); Word files are download-only. Renders a
 * "No CV" note (card) or nothing (row) when the application has no file.
 */
export default function ResumeActions({
  workerId,
  candidateName,
  resumePath,
  variant = "card",
}: ResumeActionsProps) {
  const { t } = useLanguage();
  const { hasResume, canView, busy, view, download } = useResumeFile(
    workerId,
    candidateName,
    resumePath,
  );

  if (!hasResume) {
    return variant === "card" ? <span className="muted-note">{t("applications.noResume")}</span> : null;
  }

  if (variant === "row") {
    return (
      <>
        {canView && (
          <button
            type="button"
            className="row-action"
            onClick={view}
            disabled={busy !== null}
            aria-label={t("applications.cv.viewFor", { name: candidateName })}
          >
            <Eye size={14} aria-hidden="true" />
            {t("applications.cv.short")}
          </button>
        )}
        <button
          type="button"
          className="row-action row-action--icon"
          onClick={download}
          disabled={busy !== null}
          aria-label={t("applications.cv.downloadFor", { name: candidateName })}
          title={t("applications.cv.download")}
        >
          <Download size={14} aria-hidden="true" />
        </button>
      </>
    );
  }

  return (
    <div className="resume-actions">
      {canView && (
        <Button variant="secondary" icon={<Eye size={15} />} onClick={view} loading={busy === "view"}>
          {t("applications.cv.view")}
        </Button>
      )}
      <Button
        variant={canView ? "ghost" : "secondary"}
        icon={<Download size={15} />}
        onClick={download}
        loading={busy === "download"}
      >
        {t("applications.cv.download")}
      </Button>
    </div>
  );
}
