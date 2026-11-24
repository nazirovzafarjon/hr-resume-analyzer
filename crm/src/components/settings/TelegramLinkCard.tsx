import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Send, Unlink } from "lucide-react";
import Card from "../ui/Card";
import Button from "../ui/Button";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import {
  createTelegramLinkToken,
  deleteTelegramLink,
  getTelegramLink,
  type TelegramKind,
  type TelegramLinkStatus,
} from "../../services/telegramService";
import { getErrorMessage } from "../../utils/apiError";

/** How often the card re-checks the link while the user is in Telegram. */
const POLL_MS = 3000;

type Props = {
  kind: TelegramKind;
  /** Render nothing (instead of a notice) when the server has no bot configured. */
  hideWhenDisabled?: boolean;
};

/**
 * Connect / disconnect the bot for the signed-in HR user or candidate.
 *
 * "Connect" asks the API for a single-use deep link and opens it in Telegram;
 * the user presses Start there and the card notices the new link by polling
 * until the link expires.
 */
export default function TelegramLinkCard({ kind, hideWhenDisabled = false }: Props) {
  const { t } = useLanguage();
  const notify = useNotify();
  const [status, setStatus] = useState<TelegramLinkStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ link: string; expiresAt: number } | null>(null);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await getTelegramLink(kind);
      setStatus(next);
      return next;
    } catch {
      return null;
    }
  }, [kind]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // While a deep link is outstanding, poll until it is used or expires.
  useEffect(() => {
    if (!pending) return;
    const tick = async () => {
      const next = await refresh();
      if (next?.linked) {
        setPending(null);
        notify.success(t("telegram.connected"));
        return;
      }
      if (Date.now() >= pending.expiresAt) {
        setPending(null);
        return;
      }
      timer.current = window.setTimeout(tick, POLL_MS);
    };
    timer.current = window.setTimeout(tick, POLL_MS);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [pending, refresh, notify, t]);

  async function connect() {
    setBusy(true);
    try {
      const token = await createTelegramLinkToken(kind);
      setPending({ link: token.deep_link, expiresAt: new Date(token.expires_at).getTime() });
      window.open(token.deep_link, "_blank", "noopener,noreferrer");
    } catch (error) {
      notify.error(t("telegram.connectFailed"), getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await deleteTelegramLink(kind);
      await refresh();
      notify.success(t("telegram.disconnected"));
    } catch (error) {
      notify.error(t("telegram.disconnectFailed"), getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;
  if (!status.enabled && hideWhenDisabled) return null;

  const subtitle = kind === "hr" ? t("telegram.subtitleHr") : t("telegram.subtitleCandidate");

  return (
    <Card title={t("telegram.title")} subtitle={subtitle} icon={<Send size={18} />}>
      {!status.enabled ? (
        <p className="field-hint">{t("telegram.notConfigured")}</p>
      ) : status.linked ? (
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "var(--space-md)", justifyContent: "space-between" }}>
          <div>
            <p style={{ margin: 0 }}>
              {t("telegram.linkedAs", {
                name: status.username ? `@${status.username}` : status.first_name ?? "Telegram",
              })}
            </p>
            {status.is_active === false && (
              <p className="field-hint" style={{ margin: "var(--space-xs) 0 0" }}>
                {t("telegram.blocked")}
              </p>
            )}
          </div>
          <Button variant="danger-subtle" icon={<Unlink size={16} />} loading={busy} onClick={disconnect}>
            {t("telegram.disconnect")}
          </Button>
        </div>
      ) : (
        <div style={{ display: "grid", gap: "var(--space-md)" }}>
          <p className="field-hint" style={{ margin: 0 }}>
            {pending ? t("telegram.waiting") : t("telegram.howTo")}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-sm)" }}>
            <Button icon={<Send size={16} />} loading={busy} onClick={connect}>
              {pending ? t("telegram.newLink") : t("telegram.connect")}
            </Button>
            {pending && (
              <Button
                variant="secondary"
                icon={<ExternalLink size={16} />}
                onClick={() => window.open(pending.link, "_blank", "noopener,noreferrer")}
              >
                {t("telegram.openAgain")}
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
