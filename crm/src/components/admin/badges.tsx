import Badge, { type BadgeTone } from "../ui/Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import type { HealthStatus } from "../../types/admin";

const HEALTH_TONES: Record<HealthStatus, BadgeTone> = {
  healthy: "success",
  configured: "info",
  degraded: "warning",
  down: "danger",
  not_configured: "neutral",
};

/** Health state chip (always text + colour, never colour alone). */
export function HealthBadge({ status }: { status: HealthStatus }) {
  const { t } = useLanguage();
  return (
    <Badge tone={HEALTH_TONES[status] ?? "neutral"} dot>
      {t(`admin.health.status.${status}`)}
    </Badge>
  );
}

/** Active / inactive account chip. */
export function AccountStatusBadge({ active }: { active: boolean }) {
  const { t } = useLanguage();
  return (
    <Badge tone={active ? "success" : "neutral"} dot>
      {active ? t("admin.users.active") : t("admin.users.inactive")}
    </Badge>
  );
}

/** Admin / HR role chip. */
export function RoleBadge({ admin }: { admin: boolean }) {
  const { t } = useLanguage();
  return <Badge tone={admin ? "primary" : "info"}>{admin ? t("admin.users.roleAdmin") : t("admin.users.roleHr")}</Badge>;
}

/** Success / failure chip for an AI attempt. */
export function RunStatusBadge({ status }: { status: "completed" | "failed" }) {
  const { t } = useLanguage();
  return (
    <Badge tone={status === "completed" ? "success" : "danger"} dot>
      {t(`admin.ai.runStatus.${status}`)}
    </Badge>
  );
}

/** Formats an AI score, or an em dash when the application was never analysed. */
export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined || !Number.isFinite(score) ? "—" : `${Math.round(score)}%`;
}
