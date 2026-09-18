/**
 * Success state shown after a public application submission succeeds.
 * Replaces the form so the candidate cannot (and need not) submit again.
 */

type ApplicationSuccessProps = {
  position?: string;
  company?: string;
};

export default function ApplicationSuccess({ position, company }: ApplicationSuccessProps) {
  return (
    <section className="apply-template apply-template--success" aria-label="Application submitted">
      <div className="apply-success" role="status">
        <div className="apply-success-icon" aria-hidden="true">
          ✓
        </div>
        <h1 className="apply-title">Application submitted successfully</h1>
        <p className="apply-description">
          Thank you for applying{position ? ` for ${position}` : ""}
          {company ? ` at ${company}` : ""}.
        </p>
        <p className="apply-description">
          Your application has been received successfully. You can now close
          this page.
        </p>
      </div>
    </section>
  );
}
