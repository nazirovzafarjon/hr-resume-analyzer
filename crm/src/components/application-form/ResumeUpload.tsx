/**
 * Resume upload control for `file` fields on the fixed public template.
 *
 * The native file input stays in the DOM (visually hidden but focusable), so
 * keyboard and screen-reader users get the platform picker, while the drop
 * zone around it adds drag & drop. The file is only held in memory here; it
 * travels with the final multipart submission, exactly as before.
 */

import { useRef, useState, type DragEvent } from "react";
import { CloudUpload, FileText } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import { MAX_RESUME_SIZE_MB, RESUME_ACCEPT } from "../../utils/applicationFields";

type ResumeUploadProps = {
  inputId: string;
  file: File | null;
  required: boolean;
  disabled?: boolean;
  invalid: boolean;
  describedBy?: string;
  onFileChange?: (file: File | null) => void;
};

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ResumeUpload({
  inputId,
  file,
  required,
  disabled,
  invalid,
  describedBy,
  onFileChange,
}: ResumeUploadProps) {
  const { t } = useLanguage();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const interactive = !disabled && Boolean(onFileChange);

  function pick(next: File | null | undefined) {
    if (next) onFileChange?.(next);
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    if (!interactive) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragging(true);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    if (!interactive) return;
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files?.[0]);
  }

  const input = (
    <input
      ref={inputRef}
      id={inputId}
      type="file"
      className="sr-only apply-upload-input"
      accept={RESUME_ACCEPT}
      disabled={!interactive}
      required={required && !file}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      onChange={(event) => {
        pick(event.target.files?.[0]);
        // Clear so choosing the same file again (after Remove) still fires.
        event.target.value = "";
      }}
    />
  );

  // The input keeps one stable position in the tree for both states, so a
  // keyboard user who picks a file does not lose focus when the view swaps.
  return (
    <div className="apply-upload-wrap">
      {input}
      {file ? (
        <div className={`apply-upload-file${invalid ? " apply-upload-file--error" : ""}`}>
          <span className="apply-upload-file-icon" aria-hidden="true">
            <FileText size={20} />
          </span>
          <span className="apply-upload-file-text">
            <span className="apply-upload-file-name">{file.name}</span>
            <span className="apply-upload-file-size">{formatSize(file.size)}</span>
          </span>
          <span className="apply-upload-file-actions">
            <button
              type="button"
              className="row-action"
              onClick={() => inputRef.current?.click()}
              disabled={!interactive}
              aria-label={t("apply.upload.replaceAria", { name: file.name })}
            >
              {t("apply.upload.replace")}
            </button>
            <button
              type="button"
              className="row-action row-action--danger"
              onClick={() => onFileChange?.(null)}
              disabled={!interactive}
              aria-label={t("apply.upload.removeAria", { name: file.name })}
            >
              {t("apply.upload.remove")}
            </button>
          </span>
        </div>
      ) : (
        <div
          className={[
            "apply-upload",
            dragging ? "apply-upload--dragging" : "",
            invalid ? "apply-upload--error" : "",
            interactive ? "" : "apply-upload--disabled",
          ]
            .filter(Boolean)
            .join(" ")}
          onDragOver={onDragOver}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          // Mouse convenience: the whole zone opens the picker. Keyboard users
          // reach the (focusable) native input directly.
          onClick={(event) => {
            if (interactive && !(event.target instanceof HTMLLabelElement)) {
              inputRef.current?.click();
            }
          }}
        >
          <span className="apply-upload-icon" aria-hidden="true">
            <CloudUpload size={22} />
          </span>
          <p className="apply-upload-title">
            {dragging ? t("apply.upload.dropActive") : t("apply.upload.title")}
          </p>
          <p className="apply-upload-text">
            {t("apply.upload.drop")}{" "}
            <label htmlFor={inputId} className="apply-upload-browse">
              {t("apply.upload.choose")}
            </label>
          </p>
          <p className="apply-upload-hint">{t("apply.upload.hint", { size: MAX_RESUME_SIZE_MB })}</p>
        </div>
      )}
    </div>
  );
}
