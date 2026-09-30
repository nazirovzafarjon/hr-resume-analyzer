import { useCallback, useState } from "react";
import { fetchResume } from "../services/applicationsService";
import { ApiError } from "../utils/apiError";
import { useNotify } from "../contexts/ToastContext";
import { useLanguage } from "../contexts/LanguageContext";

/** Extensions a browser tab can display; the rest are download-only. */
const VIEWABLE = new Set(["pdf", "txt"]);

export function resumeExtension(resumePath: string | null | undefined): string {
  const match = /\.([a-z0-9]+)$/i.exec(resumePath ?? "");
  return match ? match[1].toLowerCase() : "";
}

/** Same naming as the backend's Content-Disposition ("Jane Doe - CV.pdf"). */
function downloadName(candidateName: string, extension: string): string {
  const cleaned = candidateName.replace(/[^\p{L}\p{N}_ .-]+/gu, "").replace(/\s+/g, " ").trim();
  return `${cleaned || "Candidate"} - CV${extension ? `.${extension}` : ""}`;
}

/**
 * View/download a candidate's CV through the authenticated endpoint.
 *
 * The file arrives as a Blob (so the bearer token is used) and is handed to
 * the browser through a short-lived object URL. For "View" the tab is opened
 * synchronously inside the click, otherwise popup blockers would stop it.
 */
export function useResumeFile(workerId: number, candidateName: string, resumePath: string) {
  const { t } = useLanguage();
  const notify = useNotify();
  const [busy, setBusy] = useState<"view" | "download" | null>(null);
  const extension = resumeExtension(resumePath);
  const hasResume = Boolean(resumePath);
  const canView = hasResume && VIEWABLE.has(extension);

  const fail = useCallback(
    (error: unknown) => {
      const message =
        error instanceof ApiError && error.status === 404
          ? error.message
          : t("applications.cv.loadFailed");
      notify.error(t("applications.cv.unavailableTitle"), message);
    },
    [notify, t],
  );

  const view = useCallback(async () => {
    if (!canView || busy) return;
    const tab = window.open("", "_blank");
    setBusy("view");
    try {
      const blob = await fetchResume(workerId);
      const url = URL.createObjectURL(blob);
      if (tab) {
        tab.opener = null;
        tab.location.href = url;
      } else {
        window.open(url, "_blank", "noopener");
      }
      // The tab has loaded it by then; release the memory.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      tab?.close();
      fail(error);
    } finally {
      setBusy(null);
    }
  }, [busy, canView, fail, workerId]);

  const download = useCallback(async () => {
    if (!hasResume || busy) return;
    setBusy("download");
    try {
      const blob = await fetchResume(workerId, true);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = downloadName(candidateName, extension);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (error) {
      fail(error);
    } finally {
      setBusy(null);
    }
  }, [busy, candidateName, extension, fail, hasResume, workerId]);

  return { hasResume, canView, extension, busy, view, download };
}
