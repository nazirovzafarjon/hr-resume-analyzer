import { useEffect, useState, type ChangeEvent } from "react";
import { User, Palette, Globe, Shield, Sun, Moon, Monitor, Check, Upload, Trash2 } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import TextInput from "../../components/forms/TextInput";
import PasswordInput from "../../components/auth/PasswordInput";
import PasswordRequirements from "../../components/auth/PasswordRequirements";
import AuthMessage from "../../components/auth/AuthMessage";
import ErrorState from "../../components/ui/ErrorState";
import { Skeleton, SkeletonText } from "../../components/ui/Skeleton";
import Tabs from "../../components/ui/Tabs";
import { useAuth } from "../../context/AuthContext";
import { useTheme, type Theme } from "../../contexts/ThemeContext";
import { useLanguage, type Language } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import {
  changePassword,
  getCurrentUser,
  profileImageUrl,
  removeProfileImage,
  updateProfile,
  uploadProfileImage,
} from "../../services/settingsService";
import { getErrorMessage } from "../../utils/apiError";
import { getPasswordError, isValidEmail } from "../../utils/validate";
import type { UserProfile } from "../../types/user";

/** Mirrors the backend's PROFILE_IMAGE_MAX_SIZE_MB (app/core/config.py). */
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
/** Same formats the backend accepts (JPG/JPEG, PNG, WEBP). */
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** Feedback shown under one section (success or error). */
type Feedback = { kind: "success" | "error"; text: string } | null;

/** Initials for the avatar placeholder ("Jane Doe" -> "JD"). */
function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "HR";
  return parts
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

type TabKey = "profile" | "appearance" | "language" | "security";

/** /settings — the signed-in HR user's account, appearance, language and security. */
export default function SettingsPage() {
  const { signIn } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useLanguage();
  const notify = useNotify();

  const [activeTab, setActiveTab] = useState<TabKey>("profile");

  // Loaded profile + page state.
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Profile form (name + email) and its feedback.
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [profileFeedback, setProfileFeedback] = useState<Feedback>(null);
  const [saving, setSaving] = useState(false);

  // Profile image upload/remove.
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageFeedback, setImageFeedback] = useState<Feedback>(null);

  // Password change form and its feedback.
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [currentPasswordError, setCurrentPasswordError] = useState<string | null>(null);
  const [newPasswordError, setNewPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [passwordFeedback, setPasswordFeedback] = useState<Feedback>(null);
  const [changingPassword, setChangingPassword] = useState(false);

  // Load the current profile once when the page opens.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getCurrentUser();
        if (cancelled) return;
        setProfile(data);
        setName(data.full_name);
        setEmail(data.email);
        setLoadError(null);
      } catch (error) {
        if (!cancelled) setLoadError(getErrorMessage(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Apply a fresh profile to every piece of state that mirrors it. */
  function applyProfile(data: UserProfile) {
    setProfile(data);
    setName(data.full_name);
    setEmail(data.email);
    setImagePreview(null);
  }

  async function handleSaveProfile() {
    setProfileFeedback(null);
    const nextNameError = name.trim() ? null : t("auth.nameRequired") || "Full name is required.";
    const nextEmailError = !isValidEmail(email)
      ? t("auth.invalidEmail") || "Enter a valid email address."
      : null;
    setNameError(nextNameError);
    setEmailError(nextEmailError);
    if (nextNameError || nextEmailError) return;

    setSaving(true);
    try {
      const data = await updateProfile({
        full_name: name.trim(),
        email: email.trim(),
      });
      applyProfile(data);
      const msg = t("toast.profileSaved") || "Profile updated successfully.";
      setProfileFeedback({ kind: "success", text: msg });
      notify.success(msg);
    } catch (error) {
      const errMsg = getErrorMessage(error);
      setProfileFeedback({ kind: "error", text: errMsg });
      notify.error(t("toast.saveFailed") || "Failed to update profile", errMsg);
    } finally {
      setSaving(false);
    }
  }

  /** Validate the chosen file, preview it and upload it right away. */
  async function handleFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file later
    setImageFeedback(null);
    if (!file) return;

    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setImageFeedback({
        kind: "error",
        text: "Unsupported file type. Please choose a JPG, PNG or WEBP image.",
      });
      return;
    }
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      setImageFeedback({
        kind: "error",
        text: "The image is too large. Please choose a file of at most 5 MB.",
      });
      return;
    }

    // Show the chosen image immediately while it uploads.
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);
    setImageBusy(true);
    try {
      const data = await uploadProfileImage(file);
      applyProfile(data);
      const msg = t("toast.profileSaved") || "Profile image updated.";
      setImageFeedback({ kind: "success", text: msg });
      notify.success(msg);
    } catch (error) {
      const errMsg = getErrorMessage(error);
      setImageFeedback({ kind: "error", text: errMsg });
      notify.error(t("toast.saveFailed") || "Upload failed", errMsg);
    } finally {
      URL.revokeObjectURL(previewUrl);
      setImageBusy(false);
    }
  }

  async function handleRemoveImage() {
    setImageFeedback(null);
    setImageBusy(true);
    try {
      const data = await removeProfileImage();
      applyProfile(data);
      const msg = t("toast.profileSaved") || "Profile image removed.";
      setImageFeedback({ kind: "success", text: msg });
      notify.success(msg);
    } catch (error) {
      const errMsg = getErrorMessage(error);
      setImageFeedback({ kind: "error", text: errMsg });
      notify.error(t("toast.saveFailed") || "Remove failed", errMsg);
    } finally {
      setImageBusy(false);
    }
  }

  async function handleChangePassword() {
    setPasswordFeedback(null);
    const nextCurrentError = currentPassword ? null : t("auth.currentPasswordRequired") || "Current password is required.";
    const nextNewError = getPasswordError(newPassword);
    const nextConfirmError =
      confirmPassword === newPassword ? null : t("auth.passwordMismatch") || "Passwords do not match.";
    setCurrentPasswordError(nextCurrentError);
    setNewPasswordError(nextNewError);
    setConfirmError(nextConfirmError);
    if (nextCurrentError || nextNewError || nextConfirmError) return;

    setChangingPassword(true);
    try {
      const tokens = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      signIn(tokens);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      const msg = t("toast.passwordChanged") || "Password changed successfully.";
      setPasswordFeedback({ kind: "success", text: msg });
      notify.success(msg);
    } catch (error) {
      const errMsg = getErrorMessage(error);
      setPasswordFeedback({ kind: "error", text: errMsg });
      notify.error(t("toast.saveFailed") || "Password change failed", errMsg);
    } finally {
      setChangingPassword(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("settings.title") || "Settings"} description={t("settings.description") || "Manage your account and preferences."} />
        <Card>
          <Skeleton variant="title" />
          <SkeletonText lines={3} />
        </Card>
      </div>
    );
  }

  if (loadError || !profile) {
    return (
      <div className="page">
        <PageHeader title={t("settings.title") || "Settings"} description={t("settings.description") || "Manage your account and preferences."} />
        <ErrorState
          message={loadError ?? (t("common.error") || "Something went wrong.")}
          action={
            <Button onClick={() => window.location.reload()}>{t("common.retry") || "Try again"}</Button>
          }
        />
      </div>
    );
  }

  const avatarSrc = imagePreview ?? profileImageUrl(profile.profile_image);

  const tabItems = [
    { key: "profile", label: t("settings.profile") || "Profile", icon: <User size={16} /> },
    { key: "appearance", label: t("settings.appearance") || "Appearance", icon: <Palette size={16} /> },
    { key: "language", label: t("settings.language") || "Language", icon: <Globe size={16} /> },
    { key: "security", label: t("settings.password") || "Security", icon: <Shield size={16} /> },
  ];

  const themes: { key: Theme; label: string; icon: typeof Sun; desc: string }[] = [
    { key: "light", label: t("settings.themeLight") || "Light", icon: Sun, desc: "Clean, high-contrast crisp theme" },
    { key: "dark", label: t("settings.themeDark") || "Dark", icon: Moon, desc: "Calm, low-light surface hierarchy" },
    { key: "system", label: t("settings.themeSystem") || "System", icon: Monitor, desc: "Syncs with your operating system" },
  ];

  const languages: { key: Language; name: string; nativeName: string }[] = [
    { key: "uz", name: "Uzbek (Latin)", nativeName: "O'zbekcha" },
    { key: "en", name: "English", nativeName: "English" },
    { key: "ru", name: "Russian", nativeName: "Русский" },
    { key: "kiril", name: "Uzbek (Cyrillic)", nativeName: "Ўзбекча" },
  ];

  return (
    <div className="page page--settings">
      <PageMeta title={t("nav.settings")} noindex />
      <PageHeader
        title={t("settings.title") || "Settings"}
        description={t("settings.description") || "Manage your account, theme, language, and security settings."}
      />

      <div style={{ marginBottom: "var(--space-xl)" }}>
        <Tabs
          items={tabItems.map((t) => ({ id: t.key, label: t.label, icon: t.icon }))}
          activeId={activeTab}
          onChange={(k) => setActiveTab(k as TabKey)}
          ariaLabel="Settings navigation"
        />
      </div>

      {activeTab === "profile" && (
        <div className="stack">
          <Card title={t("settings.profile") || "Profile"} subtitle="Manage your name, email and avatar.">
            <div className="settings-profile-row">
              <span className="settings-avatar" aria-hidden="true">
                {avatarSrc ? (
                  <img src={avatarSrc} alt="" className="settings-avatar-img" />
                ) : (
                  <span className="settings-avatar-initials">{initialsOf(name || profile.full_name)}</span>
                )}
              </span>

              <div className="settings-avatar-actions">
                <label className="btn btn--secondary btn--sm">
                  <Upload size={14} style={{ marginRight: "4px" }} />
                  {imageBusy ? (t("common.loading") || "Uploading…") : "Upload picture"}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="visually-hidden"
                    onChange={handleFileSelected}
                    disabled={imageBusy}
                  />
                </label>
                {profile.profile_image && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRemoveImage}
                    disabled={imageBusy}
                    icon={<Trash2 size={14} />}
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>

            {imageFeedback && (
              <AuthMessage type={imageFeedback.kind}>{imageFeedback.text}</AuthMessage>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSaveProfile();
              }}
              style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)", marginTop: "var(--space-xl)" }}
            >
              <TextInput
                label={t("settings.name") || "Full Name"}
                value={name}
                onChange={setName}
                error={nameError || undefined}
                required
              />
              <TextInput
                label={t("settings.email") || "Email"}
                type="email"
                value={email}
                onChange={setEmail}
                error={emailError || undefined}
                required
              />

              {profileFeedback && (
                <AuthMessage type={profileFeedback.kind}>{profileFeedback.text}</AuthMessage>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button type="submit" loading={saving}>
                  {t("settings.saveChanges") || "Save changes"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {activeTab === "appearance" && (
        <Card title={t("settings.appearance") || "Appearance"} subtitle={t("appearance.title") || "Choose how Resume Analyzer looks to you."}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-lg)" }}>
            {themes.map((item) => {
              const Icon = item.icon;
              const isSelected = theme === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setTheme(item.key);
                    notify.success(t("toast.settingsSaved") || "Theme updated");
                  }}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    gap: "var(--space-md)",
                    padding: "var(--space-xl)",
                    borderRadius: "var(--radius-lg)",
                    border: `2px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                    background: isSelected ? "var(--color-primary-subtle)" : "var(--color-surface)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all var(--transition-fast)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                    <span style={{ color: isSelected ? "var(--color-primary)" : "var(--color-text-secondary)" }}>
                      <Icon size={24} />
                    </span>
                    {isSelected && (
                      <span style={{ color: "var(--color-primary)", display: "flex", alignItems: "center" }}>
                        <Check size={18} />
                      </span>
                    )}
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "var(--text-base)", fontWeight: "var(--font-semibold)", color: "var(--color-text)" }}>
                      {item.label}
                    </h3>
                    <p style={{ margin: "4px 0 0", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                      {item.desc}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {activeTab === "language" && (
        <Card title={t("settings.language") || "Language"} subtitle="Select your preferred language. Updates across the application immediately.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-lg)" }}>
            {languages.map((item) => {
              const isSelected = language === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setLanguage(item.key);
                    notify.success(t("toast.settingsSaved") || "Language updated");
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "var(--space-xl)",
                    borderRadius: "var(--radius-lg)",
                    border: `2px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                    background: isSelected ? "var(--color-primary-subtle)" : "var(--color-surface)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all var(--transition-fast)",
                  }}
                >
                  <div>
                    <span style={{ fontSize: "var(--text-md)", fontWeight: "var(--font-semibold)", color: "var(--color-text)" }}>
                      {item.nativeName}
                    </span>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "2px" }}>
                      {item.name}
                    </div>
                  </div>
                  {isSelected && (
                    <span style={{ color: "var(--color-primary)" }}>
                      <Check size={18} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {activeTab === "security" && (
        <Card title={t("settings.password") || "Security"} subtitle="Update your account password.">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleChangePassword();
            }}
            style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)", maxWidth: "540px" }}
          >
            <PasswordInput
              label={t("auth.currentPassword") || "Current Password"}
              value={currentPassword}
              onChange={(v) => setCurrentPassword(v)}
              error={currentPasswordError || undefined}
            />
            <div>
              <PasswordInput
                label={t("auth.newPassword") || "New Password"}
                value={newPassword}
                onChange={(v) => setNewPassword(v)}
                error={newPasswordError || undefined}
              />
              <div style={{ marginTop: "var(--space-sm)" }}>
                <PasswordRequirements password={newPassword} />
              </div>
            </div>
            <PasswordInput
              label={t("auth.confirmPassword") || "Confirm Password"}
              value={confirmPassword}
              onChange={(v) => setConfirmPassword(v)}
              error={confirmError || undefined}
            />

            {passwordFeedback && (
              <AuthMessage type={passwordFeedback.kind}>{passwordFeedback.text}</AuthMessage>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button type="submit" loading={changingPassword}>
                {t("auth.changePassword") || "Change password"}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
