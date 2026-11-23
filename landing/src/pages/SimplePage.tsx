import { ArrowLeft } from "lucide-react";
import { useDocumentMeta } from "../hooks/useDocumentMeta";
import { useI18n } from "../i18n";

type SimplePageProps = {
  title: string;
  text: string;
  back: string;
};

/**
 * Plain text page used for the legal placeholders and the 404. The legal
 * routes exist so footer links resolve; they state honestly that the
 * documents are still being prepared.
 */
export default function SimplePage({ title, text, back }: SimplePageProps) {
  const { t, homeHref } = useI18n();
  useDocumentMeta(`${title} — ${t.common.appName}`, text);

  return (
    <section className="simple-page" aria-labelledby="page-title">
      <div className="container simple-page-inner">
        <h1 id="page-title">{title}</h1>
        <p>{text}</p>
        <a className="btn btn--secondary" href={homeHref}>
          <ArrowLeft size={16} aria-hidden="true" />
          {back}
        </a>
      </div>
    </section>
  );
}
