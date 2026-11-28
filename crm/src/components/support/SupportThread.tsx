import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import type { SupportMessage, SupportSender } from "../../types/support";

export const SUPPORT_MESSAGE_MAX = 4000;

function formatTime(iso: string): string {
  const date = new Date(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  return date.toLocaleString(undefined, sameDay
    ? { hour: "2-digit", minute: "2-digit" }
    : { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/**
 * The messages of one support conversation, oldest first, kept scrolled to
 * the newest one. `viewer` decides which side is "mine" (right-aligned).
 */
export function SupportThread({
  messages,
  viewer,
  requesterLabel,
}: {
  messages: SupportMessage[];
  viewer: SupportSender;
  /** How the admin view names the requester's messages. */
  requesterLabel?: string;
}) {
  const { t } = useLanguage();
  const endRef = useRef<HTMLDivElement>(null);
  const lastId = messages[messages.length - 1]?.id;

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [lastId]);

  return (
    <div className="support-thread" role="log" aria-live="polite" aria-label={t("support.thread")}>
      {messages.map((message) => {
        const mine = message.sender === viewer;
        const author =
          message.sender === "admin"
            ? message.author_name
              ? `${message.author_name} · ${t("support.team")}`
              : t("support.team")
            : (requesterLabel ?? t("support.you"));
        return (
          <div key={message.id} className={`support-message${mine ? " support-message--mine" : ""}`}>
            <div className="support-message-meta">
              <span>{mine && viewer === "requester" ? t("support.you") : author}</span>
              <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
            </div>
            <div className="support-bubble">{message.body}</div>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}

/** Message box: Enter sends, Shift+Enter adds a new line. */
export function SupportComposer({
  onSend,
  placeholder,
  disabled = false,
  autoFocus = false,
}: {
  onSend: (body: string) => Promise<void>;
  placeholder: string;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const { t } = useLanguage();
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = body.trim();
    if (!text || sending || disabled) return;
    setSending(true);
    try {
      await onSend(text);
      setBody("");
    } catch {
      /* The caller reports the error; keep the text so nothing is lost. */
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit();
    }
  }

  const empty = body.trim().length === 0;
  return (
    <form className="support-composer" onSubmit={submit}>
      <label className="sr-only" htmlFor={inputId}>
        {placeholder}
      </label>
      <textarea
        id={inputId}
        ref={textareaRef}
        className="support-composer-input"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        maxLength={SUPPORT_MESSAGE_MAX}
        rows={2}
        disabled={disabled}
      />
      <button
        type="submit"
        className="support-send"
        disabled={empty || sending || disabled}
        aria-label={t("support.send")}
        title={t("support.send")}
      >
        <SendHorizontal size={18} aria-hidden="true" />
      </button>
    </form>
  );
}
