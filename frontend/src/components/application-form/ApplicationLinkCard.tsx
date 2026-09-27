/**
 * Public application link card (HR-facing): the shareable link of the job's
 * application form with one-click copy and open. This is the product's own
 * public application URL — no external form generator involved.
 */

import { useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { copyToClipboard } from "../../utils/clipboard";

type ApplicationLinkCardProps = {
  token: string;
  jobTitle?: string;
  onRegenerate?: () => void;
  regenerating?: boolean;
};

export function applicationUrl(token: string): string {
  return `${window.location.origin}/apply/${token}`;
}

export default function ApplicationLinkCard({
  token,
  jobTitle,
  onRegenerate,
  regenerating,
}: ApplicationLinkCardProps) {
  const { t } = useLanguage();
  const notify = useNotify();
  const [copied, setCopied] = useState(false);
  const [confirmingRegenerate, setConfirmingRegenerate] = useState(false);
  const url = token ? applicationUrl(token) : null;

  async function handleCopy() {
    if (!url) return;
    const ok = await copyToClipboard(url);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
      notify.success(t("applicationForm.link.copiedToast") || "Link copied");
    } else {
      notify.error(
        t("applicationForm.link.copyFailedToast") || "Couldn't copy the link",
        t("applicationForm.link.copyFailedHint") || "Select the link text and copy it manually.",
      );
    }
  }

  function handleRegenerateConfirm() {
    setConfirmingRegenerate(false);
    onRegenerate?.();
  }

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2 className="card-title">{t("applicationForm.link.title") || "Application Link"}</h2>
          <p className="card-subtitle">
            {t("applicationForm.link.subtitle") ||
              "Candidates apply through this link — share it via email, LinkedIn or messaging apps."}
          </p>
        </div>
      </header>
      <div className="apply-link-card">
        <div className="apply-success-icon" aria-hidden="true">
          <Check size={18} />
        </div>
        <div className="apply-link-body">
          {jobTitle && (
            <h3>
              {(t("applicationForm.link.liveFor") || 'Application link is live for "{title}"').replace(
                "{title}",
                jobTitle,
              )}
            </h3>
          )}
          {url ? (
            <>
              <input
                className="apply-link-url apply-link-url-input"
                type="text"
                readOnly
                value={url}
                onFocus={(event) => event.currentTarget.select()}
                aria-label={t("applicationForm.link.title") || "Application Link"}
              />
              <div className="form-success-actions">
                <Button variant="secondary" onClick={handleCopy} icon={copied ? <Check size={15} /> : <Copy size={15} />}>
                  {copied
                    ? t("applicationForm.link.copied") || "Copied"
                    : t("applicationForm.link.copyLink") || "Copy Link"}
                </Button>
                <a className="btn btn--primary" href={url} target="_blank" rel="noreferrer">
                  <ExternalLink size={15} style={{ marginRight: 6 }} />
                  {t("applicationForm.link.open") || "Open Application"}
                </a>
                {onRegenerate && (
                  <Button
                    variant="ghost"
                    onClick={() => setConfirmingRegenerate(true)}
                    loading={regenerating}
                    disabled={regenerating}
                  >
                    {t("applicationForm.link.regenerate") || "Regenerate link"}
                  </Button>
                )}
              </div>
              <p className="muted-note">
                {t("applicationForm.link.regenerateNote") ||
                  "Regenerating creates a new link and immediately stops the old one."}
              </p>
            </>
          ) : (
            <p className="muted-note">
              {t("applicationForm.link.noLinkYet") ||
                "This job has no published application link yet. Publish the form from the builder above."}
            </p>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmingRegenerate}
        title={t("applicationForm.link.regenerateConfirmTitle") || "Regenerate the application link?"}
        message={
          t("applicationForm.link.regenerateConfirmMessage") ||
          "The current link will stop working immediately. Anyone who still has it won't be able to apply."
        }
        confirmLabel={t("applicationForm.link.regenerate") || "Regenerate link"}
        cancelLabel={t("jobs.cancel") || "Cancel"}
        danger
        onConfirm={handleRegenerateConfirm}
        onCancel={() => setConfirmingRegenerate(false)}
      />
    </section>
  );
}
