/**
 * Public application link card (HR-facing): the shareable link of the job's
 * application form with one-click copy and open. Replaces the old
 * Google-Form success card — this is OUR OWN public application URL.
 */

import { useState } from "react";
import Button from "../ui/Button";

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
  const [copied, setCopied] = useState(false);
  const url = token ? applicationUrl(token) : null;

  async function handleCopy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Clipboard may be unavailable — feedback still shows below.
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2 className="card-title">Application Link</h2>
          <p className="card-subtitle">
            Candidates apply through this link — share it via email, LinkedIn or
            messaging apps.
          </p>
        </div>
      </header>
      <div className="apply-link-card">
        <div className="apply-success-icon" aria-hidden="true">
          ✓
        </div>
        <div className="apply-link-body">
          {jobTitle && <h3>Application link is live for “{jobTitle}”</h3>}
          {url ? (
            <>
              <p className="apply-link-url">{url}</p>
              <div className="form-success-actions">
                <Button variant="secondary" onClick={handleCopy}>
                  {copied ? "✓ Copied" : "Copy Link"}
                </Button>
                <a className="btn btn--primary" href={url} target="_blank" rel="noreferrer">
                  Open Application
                </a>
                {onRegenerate && (
                  <Button variant="ghost" onClick={onRegenerate} loading={regenerating} disabled={regenerating}>
                    Regenerate link
                  </Button>
                )}
              </div>
              <p className="muted-note">Regenerating creates a new link and immediately stops the old one.</p>
            </>
          ) : (
            <p className="muted-note">This job has no published application link yet. Publish the form from the builder above.</p>
          )}
        </div>
      </div>
    </section>
  );
}
