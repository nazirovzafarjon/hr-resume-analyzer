/**
 * Small inline loading indicator used inside table cells and list rows.
 * `role="status"` keeps it announced politely for assistive tech.
 */
export default function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="spinner" role="status" aria-label={label}>
      <span aria-hidden="true" className="spinner-dot" />
      <span aria-hidden="true" className="spinner-dot" />
      <span aria-hidden="true" className="spinner-dot" />
    </span>
  );
}
