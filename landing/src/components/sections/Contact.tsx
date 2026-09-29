import { useRef, useState, type FormEvent } from "react";
import { CircleAlert, ArrowRight, CircleCheck, LoaderCircle, Mail, Send } from "lucide-react";
import { useI18n } from "../../i18n";
import { CONTACT_EMAIL, appLinks } from "../../lib/config";
import { ContactError, sendContactMessage, type ContactErrorKind } from "../../lib/contact";
import { useSignedIn } from "../../hooks/useSignedIn";

type Field = "firstName" | "lastName" | "email" | "message";
type Values = Record<Field, string>;

const EMPTY: Values = { firstName: "", lastName: "", email: "", message: "" };
const FIELDS: Field[] = ["firstName", "lastName", "email", "message"];

// Mirrors the backend schema (app/schemas/contact_message.py).
const MAX_LENGTH: Record<Field, number> = { firstName: 100, lastName: 100, email: 255, message: 5000 };
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Contact section. The form posts to the backend's public contact endpoint, so
 * visitors can write without an account; the team replies to the email given.
 */
export default function Contact() {
  const { t } = useI18n();
  const c = t.contact;
  const signedIn = useSignedIn();

  return (
    <section id="contact" className="section section--alt" aria-labelledby="contact-title">
      <div className="container split split--top">
        <div className="split-copy" data-reveal>
          <p className="eyebrow">{c.eyebrow}</p>
          <h2 id="contact-title" className="section-title">{c.title}</h2>
          <p className="section-subtitle">{c.subtitle}</p>

          {CONTACT_EMAIL && (
            <a className="contact-email" href={`mailto:${CONTACT_EMAIL}`}>
              <span className="icon-tile icon-tile--sm" aria-hidden="true">
                <Mail size={16} />
              </span>
              <span>
                <span className="contact-email-label">{c.emailLabel}</span>
                <span className="contact-email-value">{CONTACT_EMAIL}</span>
              </span>
            </a>
          )}

          <p className="contact-login">
            {signedIn ? c.signedInUser : c.alreadyUser}{" "}
            <a href={signedIn ? appLinks.workspace : appLinks.login}>
              {signedIn ? c.signedInLink : c.alreadyUserLink}
              <ArrowRight size={14} aria-hidden="true" />
            </a>
          </p>
        </div>

        <div data-reveal>
          <ContactForm />
        </div>
      </div>
    </section>
  );
}

function ContactForm() {
  const { t } = useI18n();
  const c = t.contact;
  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [submitError, setSubmitError] = useState<ContactErrorKind | null>(null);
  // A ref, not state: two clicks in the same frame both see `sending === false`.
  const inFlight = useRef(false);
  const successRef = useRef<HTMLDivElement>(null);

  const submitErrorText: Record<ContactErrorKind, string> = {
    network: c.errorNetwork,
    validation: c.errorValidation,
    rateLimited: c.errorRateLimited,
    server: c.errorServer,
  };

  function validate(): Partial<Record<Field, string>> {
    const next: Partial<Record<Field, string>> = {};
    FIELDS.forEach((field) => {
      const value = values[field].trim();
      if (!value) next[field] = c.required;
      else if (value.length > MAX_LENGTH[field]) next[field] = c.tooLong.replace("{max}", String(MAX_LENGTH[field]));
    });
    if (!next.email && !EMAIL_PATTERN.test(values.email.trim())) next.email = c.invalidEmail;
    return next;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;

    const next = validate();
    setErrors(next);
    setSubmitError(null);
    const firstInvalid = FIELDS.find((field) => next[field]);
    if (firstInvalid) {
      document.getElementById(`contact-${firstInvalid}`)?.focus();
      return;
    }

    inFlight.current = true;
    setSending(true);
    try {
      await sendContactMessage({
        first_name: values.firstName.trim(),
        last_name: values.lastName.trim(),
        email: values.email.trim(),
        message: values.message.trim(),
      });
      setValues(EMPTY);
      setSent(true);
      requestAnimationFrame(() => successRef.current?.focus());
    } catch (error) {
      setSubmitError(error instanceof ContactError ? error.kind : "server");
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div
        ref={successRef}
        className="card contact-card contact-card--notice contact-card--success"
        role="status"
        tabIndex={-1}
      >
        <CircleCheck size={24} aria-hidden="true" />
        <div>
          <p className="contact-notice-title">{c.successTitle}</p>
          <p>{c.success}</p>
        </div>
        <button type="button" className="btn btn--secondary" onClick={() => setSent(false)}>
          {c.sendAnother}
        </button>
      </div>
    );
  }

  function field(name: Field, label: string, placeholder: string, autoComplete: string, multiline = false) {
    const id = `contact-${name}`;
    const errorId = `${id}-error`;
    const common = {
      id,
      name,
      value: values[name],
      placeholder,
      autoComplete,
      required: true,
      maxLength: MAX_LENGTH[name],
      disabled: sending,
      "aria-invalid": errors[name] ? true : undefined,
      "aria-describedby": errors[name] ? errorId : undefined,
      onChange: (event: { target: { value: string } }) => {
        setValues((current) => ({ ...current, [name]: event.target.value }));
        if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
      },
    };
    return (
      <div className={`field${multiline ? " field--full" : ""}`}>
        <label htmlFor={id}>{label}</label>
        {multiline ? (
          <textarea {...common} rows={5} />
        ) : (
          <input {...common} type={name === "email" ? "email" : "text"} />
        )}
        {errors[name] && (
          <p id={errorId} className="field-error">
            {errors[name]}
          </p>
        )}
      </div>
    );
  }

  return (
    <form className="card contact-card contact-form" onSubmit={onSubmit} noValidate aria-busy={sending}>
      {field("firstName", c.firstName, c.firstNamePlaceholder, "given-name")}
      {field("lastName", c.lastName, c.lastNamePlaceholder, "family-name")}
      {field("email", c.email, c.emailPlaceholder, "email")}
      {field("message", c.message, c.messagePlaceholder, "off", true)}
      {submitError && (
        <p className="field--full contact-alert" role="alert">
          <CircleAlert size={16} aria-hidden="true" />
          {submitErrorText[submitError]}
        </p>
      )}
      <div className="field--full contact-submit">
        <button type="submit" className="btn btn--lg" disabled={sending}>
          {sending ? (
            <LoaderCircle size={18} className="spin" aria-hidden="true" />
          ) : (
            <Send size={18} aria-hidden="true" />
          )}
          {sending ? c.sending : c.submit}
        </button>
        <p className="contact-hint">{c.submitHint}</p>
      </div>
    </form>
  );
}
