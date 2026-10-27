import { useEffect, useState } from "react";
import { PlugZap, Trash2 } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ConfirmDialog from "../ui/ConfirmDialog";
import ErrorState from "../ui/ErrorState";
import { SkeletonText } from "../ui/Skeleton";
import Select from "../forms/Select";
import TextInput from "../forms/TextInput";
import PasswordInput from "../auth/PasswordInput";
import AuthMessage from "../auth/AuthMessage";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import {
  getAIProvider,
  removeAIProvider,
  saveAIProvider,
  testAIProvider,
} from "../../services/settingsService";
import { getErrorMessage } from "../../utils/apiError";
import type { AIProviderInput, AIProviderName, AIProviderSettings } from "../../types/user";

const PROVIDER_LABELS: Record<AIProviderName, string> = {
  openrouter: "OpenRouter",
  groq: "Groq",
  gemini: "Google Gemini",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  anthropic: "Anthropic Claude",
  generic: "Generic OpenAI-compatible",
};

type Errors = Partial<Record<"provider" | "apiKey" | "modelId" | "baseUrl", string>>;

/**
 * Settings -> "Connect your provider and API key".
 *
 * The raw key lives only in this component's state while the user types; it
 * is cleared after a successful save and never goes to storage, the URL or
 * the console. The server only ever returns a masked hint.
 */
export default function AIProviderSettings() {
  const { t } = useLanguage();
  const notify = useNotify();
  const [status, setStatus] = useState<AIProviderSettings | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [provider, setProvider] = useState<AIProviderName | "">("");
  const [apiKey, setApiKey] = useState("");
  const [modelId, setModelId] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  function apply(next: AIProviderSettings) {
    setStatus(next);
    setProvider(next.provider ?? "");
    setModelId(next.model_id ?? "");
    setBaseUrl(next.base_url ?? "");
    setApiKey("");
    setErrors({});
  }

  useEffect(() => {
    let cancelled = false;
    getAIProvider()
      .then((data) => !cancelled && apply(data))
      .catch(() => !cancelled && setLoadError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (loadError) {
    return <ErrorState message={t("settings.aiProvider.loadFailed")} />;
  }
  if (!status) {
    return (
      <Card title={t("settings.aiProvider.title")}>
        <SkeletonText lines={4} />
      </Card>
    );
  }

  const s = (key: string, params?: Record<string, string | number>) =>
    t(`settings.aiProvider.${key}`, params);
  // A saved key can be reused only for the provider it belongs to.
  const keepsSavedKey = status.configured && status.provider === provider;

  function validate(): AIProviderInput | null {
    const next: Errors = {};
    const key = apiKey.trim();
    const model = modelId.trim();
    if (!provider) next.provider = s("providerRequired");
    if (!key && !keepsSavedKey) next.apiKey = s("keyRequired");
    else if (key && /\s/.test(key)) next.apiKey = s("noSpaces");
    else if (key && key.length < 8) next.apiKey = s("keyTooShort");
    if (!model) next.modelId = s("modelRequired");
    else if (/\s/.test(model)) next.modelId = s("noSpaces");
    if (provider === "generic") {
      const url = baseUrl.trim();
      if (!url) next.baseUrl = "Base URL is required.";
      else if (!/^https:\/\//.test(url)) next.baseUrl = "Use https://";
    }
    setErrors(next);
    if (Object.keys(next).length > 0 || !provider) return null;
    const input: AIProviderInput = { provider, model_id: model, ...(key ? { api_key: key } : {}) };
    if (provider === "generic") input.base_url = baseUrl.trim();
    return input;
  }

  async function handleSave() {
    setFeedback(null);
    const input = validate();
    if (!input) return;
    setBusy("save");
    try {
      apply(await saveAIProvider(input));
      notify.success(s("saved"), s("savedMessage"));
    } catch (error) {
      setFeedback({ kind: "error", text: getErrorMessage(error) });
    } finally {
      setBusy(null);
    }
  }

  async function handleTest() {
    setFeedback(null);
    const input = validate();
    if (!input) return;
    setBusy("test");
    try {
      const result = await testAIProvider(input);
      setFeedback({ kind: result.ok ? "success" : "error", text: result.message });
    } catch (error) {
      setFeedback({ kind: "error", text: getErrorMessage(error) });
    } finally {
      setBusy(null);
    }
  }

  async function handleRemove() {
    setBusy("remove");
    try {
      apply(await removeAIProvider());
      setFeedback(null);
      notify.info(s("removed"), s("removedMessage"));
    } catch (error) {
      setFeedback({ kind: "error", text: getErrorMessage(error) });
    } finally {
      setBusy(null);
      setConfirmRemove(false);
    }
  }

  const custom = status.source === "custom";
  // No own provider and no platform fallback: AI features are off for this user.
  const missing = !custom && status.required;
  const badge = custom
    ? { tone: "success" as const, label: s("usingCustom") }
    : missing
      ? { tone: "warning" as const, label: s("notConfigured") }
      : { tone: "neutral" as const, label: s("usingDefault") };

  return (
    <Card
      title={s("title")}
      subtitle={status.required ? s("subtitleRequired") : s("subtitle")}
      action={<Badge tone={badge.tone}>{badge.label}</Badge>}
    >
      <form
        className="ai-provider-form"
        onSubmit={(event) => {
          event.preventDefault();
          handleSave();
        }}
        noValidate
      >
        {!status.can_save && <AuthMessage type="error">{s("disabled")}</AuthMessage>}
        {missing && status.can_save && (
          <p className="alert alert--info" role="status">
            {s("requiredHint")}
          </p>
        )}

        <Select
          label={s("provider")}
          value={provider}
          onChange={(value) => setProvider(value as AIProviderName)}
          required
          options={[
            ...(provider ? [] : [{ value: "", label: "—" }]),
            ...status.supported_providers.map((name) => ({ value: name, label: PROVIDER_LABELS[name] ?? name })),
          ]}
        />
        {errors.provider && <p className="field-error">{errors.provider}</p>}

        <div>
          <PasswordInput
            label={keepsSavedKey ? s("apiKeyReplace") : s("apiKey")}
            value={apiKey}
            onChange={setApiKey}
            autoComplete="off"
            error={errors.apiKey}
          />
          <p className="field-hint">
            {keepsSavedKey && status.masked_api_key
              ? `${s("savedKey", { masked: status.masked_api_key })} · ${s("apiKeyHint")}`
              : s("apiKeyHint")}
          </p>
        </div>

        <TextInput
          label={s("modelId")}
          value={modelId}
          onChange={setModelId}
          placeholder="deepseek/deepseek-v4.1-flash"
          hint={s("modelHint")}
          error={errors.modelId}
          autoComplete="off"
          required
        />

        {provider === "generic" && (
          <TextInput
            label={s("baseUrl") || "Base URL (required)"}
            value={baseUrl || ""}
            onChange={(v) => setBaseUrl(v)}
            placeholder="https://api.example.com/v1"
            hint="HTTPS endpoint for the OpenAI-compatible API."
            error={errors.baseUrl}
            autoComplete="off"
            required
          />
        )}

        {feedback && <AuthMessage type={feedback.kind}>{feedback.text}</AuthMessage>}

        <div className="ai-provider-actions">
          {status.configured && (
            <Button
              variant="danger-subtle"
              icon={<Trash2 size={15} />}
              onClick={() => setConfirmRemove(true)}
              disabled={busy !== null}
            >
              {s("remove")}
            </Button>
          )}
          <span className="ai-provider-actions-spacer" />
          <Button
            variant="secondary"
            icon={<PlugZap size={15} />}
            onClick={handleTest}
            loading={busy === "test"}
            disabled={busy !== null && busy !== "test"}
          >
            {s("test")}
          </Button>
          <Button
            type="submit"
            loading={busy === "save"}
            disabled={!status.can_save || (busy !== null && busy !== "save")}
          >
            {s("save")}
          </Button>
        </div>
      </form>

      <ConfirmDialog
        open={confirmRemove}
        title={s("removeTitle")}
        message={s("removeMessage")}
        confirmLabel={s("remove")}
        danger
        loading={busy === "remove"}
        onConfirm={handleRemove}
        onCancel={() => setConfirmRemove(false)}
      />
    </Card>
  );
}
