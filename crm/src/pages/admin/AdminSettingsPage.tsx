import { useState, type ReactNode } from "react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import EmptyState from "../../components/ui/EmptyState";
import { SkeletonText } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchAdminSettings, updateAdminSettings } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { formatDateTime } from "../../utils/date";
import type { AdminSettings } from "../../types/admin";

/** Yes/No chip for a configuration flag. */
function Flag({ on, onLabel, offLabel, warn = false }: { on: boolean; onLabel: string; offLabel: string; warn?: boolean }) {
  return (
    <Badge tone={on ? "success" : warn ? "warning" : "neutral"} dot>
      {on ? onLabel : offLabel}
    </Badge>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

/**
 * Admin settings: the runtime switches admins may change, plus the server's
 * environment configuration shown as read-only *status*. Secrets never reach
 * the browser (the API returns only whether they are set), and environment
 * values cannot be edited here by design.
 */
export default function AdminSettingsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const { data, loading, error, reload } = useApiQuery(fetchAdminSettings, "admin-settings");
  const [saved, setSaved] = useState<AdminSettings | null>(null);
  const [confirming, setConfirming] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const settings = saved ?? data;

  async function applyRegistration(enabled: boolean) {
    setSaving(true);
    try {
      setSaved(await updateAdminSettings({ registration_enabled: enabled }));
      notify.success(enabled ? t("admin.settings.registrationOpened") : t("admin.settings.registrationClosed"));
      setConfirming(null);
    } catch (err) {
      notify.error(t("admin.settings.saveFailed"), getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (error && !settings) {
    return (
      <div className="page">
        <PageHeader title={t("admin.settings.title")} description={t("admin.settings.description")} />
        <EmptyState
          tone="error"
          title={t("errors.loadTitle")}
          message={getErrorMessage(error, t("errors.loadMessage"))}
          action={<Button onClick={reload}>{t("common.retry")}</Button>}
        />
      </div>
    );
  }

  if (loading || !settings) {
    return (
      <div className="page">
        <PageHeader title={t("admin.settings.title")} description={t("admin.settings.description")} />
        <Card>
          <SkeletonText lines={6} />
        </Card>
      </div>
    );
  }

  const { runtime, configuration } = settings;
  const ai = configuration.ai as Record<string, unknown>;
  const email = configuration.email as Record<string, unknown>;
  const auth = configuration.auth as Record<string, unknown>;
  const platform = configuration.platform as Record<string, unknown>;
  const yes = t("common.yes");
  const no = t("common.no");

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.settings")} noindex />
      <PageHeader title={t("admin.settings.title")} description={t("admin.settings.description")} />

      <Card title={t("admin.settings.platformTitle")} subtitle={t("admin.settings.platformHint")}>
        <div className="integration-row">
          <div>
            <h3>{t("admin.settings.registration")}</h3>
            <p className="table-muted">{t("admin.settings.registrationHint")}</p>
            {/* Only after an admin changed it (the defaults row has no author). */}
            {runtime.updated_at && runtime.updated_by_email && (
              <p className="table-secondary">
                {t("admin.settings.lastChanged", {
                  date: formatDateTime(runtime.updated_at),
                  who: runtime.updated_by_email,
                })}
              </p>
            )}
          </div>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={runtime.registration_enabled}
              disabled={saving}
              onChange={(event) => setConfirming(event.target.checked)}
            />
            {runtime.registration_enabled ? t("admin.settings.open") : t("admin.settings.closed")}
          </label>
        </div>
      </Card>

      <div className="dashboard-grid dashboard-grid--even">
        <Card title={t("admin.settings.aiTitle")} subtitle={t("admin.settings.envHint")}>
          <dl className="detail-list">
            <Row label={t("admin.settings.provider")}>{String(ai.provider)}</Row>
            <Row label={t("admin.settings.model")}>{(ai.model as string | null) ?? "—"}</Row>
            <Row label={t("admin.settings.apiKey")}>
              <Flag
                on={Boolean(ai.api_key_configured)}
                onLabel={t("admin.settings.configured")}
                offLabel={t("admin.settings.notConfigured")}
                warn
              />
            </Row>
            <Row label={t("admin.settings.retries")}>
              {t("admin.settings.retriesValue", {
                count: String(ai.max_retries),
                delay: String(ai.retry_base_delay_seconds),
              })}
            </Row>
            <Row label={t("admin.settings.timeout")}>{`${String(ai.request_timeout_seconds)} s`}</Row>
            <Row label={t("admin.settings.customKeys")}>
              <Flag on={Boolean(ai.custom_keys_enabled)} onLabel={t("admin.settings.enabled")} offLabel={t("admin.settings.disabled")} />
            </Row>
            <Row label={t("admin.settings.customUsers")}>{String(ai.custom_provider_users)}</Row>
          </dl>
        </Card>

        <Card title={t("admin.settings.emailTitle")} subtitle={t("admin.settings.envHint")}>
          <dl className="detail-list">
            <Row label={t("admin.settings.provider")}>Resend</Row>
            <Row label={t("admin.settings.status")}>
              <Flag
                on={Boolean(email.configured)}
                onLabel={t("admin.settings.configured")}
                offLabel={t("admin.settings.emailLogOnly")}
                warn
              />
            </Row>
            <Row label={t("admin.settings.sender")}>
              {email.sandbox_sender ? (
                <Badge tone="warning">{t("admin.settings.sandboxSender")}</Badge>
              ) : email.sender_configured ? (
                t("admin.settings.configured")
              ) : (
                t("admin.settings.notConfigured")
              )}
            </Row>
          </dl>
        </Card>

        <Card title={t("admin.settings.authTitle")} subtitle={t("admin.settings.envHint")}>
          <dl className="detail-list">
            <Row label={t("admin.settings.googleSignIn")}>
              <Flag on={Boolean(auth.google_sign_in_configured)} onLabel={t("admin.settings.configured")} offLabel={t("admin.settings.notConfigured")} />
            </Row>
            <Row label={t("admin.settings.accessToken")}>{t("admin.settings.minutes", { count: String(auth.access_token_minutes) })}</Row>
            <Row label={t("admin.settings.refreshToken")}>{t("admin.settings.days", { count: String(auth.refresh_token_days) })}</Row>
            <Row label={t("admin.settings.secretKey")}>
              {auth.secret_key_is_default ? (
                <Badge tone="danger" dot>{t("admin.settings.secretDefault")}</Badge>
              ) : (
                <Badge tone="success" dot>{t("admin.settings.secretCustom")}</Badge>
              )}
            </Row>
          </dl>
        </Card>

        <Card title={t("admin.settings.systemTitle")} subtitle={t("admin.settings.envHint")}>
          <dl className="detail-list">
            <Row label={t("admin.settings.appName")}>{String(platform.app_name)}</Row>
            <Row label={t("admin.settings.frontendUrl")}>{String(platform.frontend_url)}</Row>
            <Row label={t("admin.settings.debug")}>
              {platform.debug ? <Badge tone="warning" dot>{yes}</Badge> : no}
            </Row>
          </dl>
        </Card>
      </div>

      <ConfirmDialog
        open={confirming !== null}
        danger={confirming === false}
        title={confirming ? t("admin.settings.openTitle") : t("admin.settings.closeTitle")}
        message={confirming ? t("admin.settings.openMessage") : t("admin.settings.closeMessage")}
        confirmLabel={confirming ? t("admin.settings.openConfirm") : t("admin.settings.closeConfirm")}
        cancelLabel={t("common.cancel")}
        loading={saving}
        onConfirm={() => confirming !== null && applyRegistration(confirming)}
        onCancel={() => setConfirming(null)}
      />
    </div>
  );
}
