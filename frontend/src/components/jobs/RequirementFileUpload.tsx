import { useRef, useState } from "react";
import Button from "../ui/Button";

type RequirementFileUploadProps = {
  fileName: string | null;
  onFileSelect: (file: File | null) => void;
  disabled?: boolean;
};

const ACCEPTED = ".pdf,.doc,.docx,.txt";

/**
 * Drag & drop requirement-document upload with a preview card.
 * Mock only — the file itself is never sent anywhere.
 */
export default function RequirementFileUpload({
  fileName,
  onFileSelect,
  disabled,
}: RequirementFileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFile(file: File | undefined) {
    if (!file) return;
    const ok = /\.(pdf|doc|docx|txt)$/i.test(file.name);
    if (!ok) {
      setError("Please upload a PDF, DOC, DOCX or TXT file.");
      return;
    }
    setError(null);
    onFileSelect(file);
  }

  return (
    <div>
      <div
        className={`dropzone${dragging ? " is-dragging" : ""}`}
        role="button"
        tabIndex={0}
        aria-label="Upload requirement document"
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
        <div className="dropzone-icon" aria-hidden="true">⇪</div>
        <p className="dropzone-title">
          {dragging ? "Drop the file to attach it" : "Drag & drop your requirement file here"}
        </p>
        <p className="dropzone-sub">or click to browse — PDF, DOC, DOCX, TXT (mock upload)</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="sr-only"
          tabIndex={-1}
          disabled={disabled}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {fileName && (
        <div className="file-preview">
          <span className="file-preview-icon" aria-hidden="true">📄</span>
          <div className="file-preview-meta">
            <p className="file-preview-name">{fileName}</p>
            <p className="file-preview-sub">Attached — will be parsed by AI (mock)</p>
          </div>
          <Button
            variant="secondary"
            onClick={() => onFileSelect(null)}
            ariaLabel="Remove attached file"
          >
            Remove
          </Button>
        </div>
      )}
    </div>
  );
}
