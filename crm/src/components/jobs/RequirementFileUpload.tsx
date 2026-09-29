import { useRef, useState } from "react";
import { FileText, UploadCloud } from "lucide-react";
import Button from "../ui/Button";
import { useLanguage } from "../../contexts/LanguageContext";

type RequirementFileUploadProps = {
  fileName: string | null;
  fileSize?: number | null;
  onFileSelect: (file: File | null) => void;
  disabled?: boolean;
};

const ACCEPTED = ".txt";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Drag & drop requirement-document upload. Limited to plain text (.txt):
 * that is the only format the app can genuinely read client-side (via
 * File.text()) without a new parsing dependency or a backend upload
 * endpoint — the real file content is folded into the AI analysis prompt
 * by the caller, not just the filename.
 */
export default function RequirementFileUpload({
  fileName,
  fileSize,
  onFileSelect,
  disabled,
}: RequirementFileUploadProps) {
  const { t } = useLanguage();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    const ok = /\.txt$/i.test(file.name);
    if (!ok) {
      setError(t("jobs.uploadRequirementFileError"));
      return;
    }
    setError(null);
    onFileSelect(file);
  }

  return (
    <div>
      {!fileName && (
        <div
          className={`dropzone${dragging ? " is-dragging" : ""}`}
          role="button"
          tabIndex={0}
          aria-label={t("jobs.uploadAriaLabel")}
          onClick={() => !disabled && inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !disabled) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (disabled) return;
            handleFile(e.dataTransfer.files?.[0]);
          }}
        >
          <div className="dropzone-icon" aria-hidden="true">
            <UploadCloud size={22} />
          </div>
          <p className="dropzone-title">
            {dragging ? t("jobs.uploadRequirementFileDrop") : t("jobs.uploadRequirementFile")}
          </p>
          <p className="dropzone-sub">{t("jobs.uploadRequirementFileSub")}</p>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="sr-only"
        tabIndex={-1}
        disabled={disabled}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {fileName && (
        <div className="file-preview">
          <span className="file-preview-icon" aria-hidden="true">
            <FileText size={20} />
          </span>
          <div className="file-preview-meta">
            <p className="file-preview-name">{fileName}</p>
            <p className="file-preview-sub">
              {t("jobs.attachedFile")}
              {typeof fileSize === "number" ? ` · ${formatFileSize(fileSize)}` : ""}
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => onFileSelect(null)}
            ariaLabel={t("jobs.removeFileAriaLabel")}
            disabled={disabled}
          >
            {t("jobs.removeFile")}
          </Button>
        </div>
      )}
    </div>
  );
}
