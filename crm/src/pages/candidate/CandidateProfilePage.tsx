import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Trash2, Upload } from "lucide-react";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormField from "../../components/forms/FormField";
import PageMeta from "../../components/seo/PageMeta";
import PasswordInput from "../../components/auth/PasswordInput";
import { candidateImageUrl } from "../../components/candidate/portalFormat";
import { PortalLoading } from "../../components/candidate/PortalStates";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import {
  changeCandidatePassword,
  removeCandidateProfileImage,
  updateCandidateProfile,
  uploadCandidateProfileImage,
} from "../../services/candidatePortalService";
import { getErrorMessage } from "../../utils/apiError";
import { isValidEmail } from "../../utils/validate";

const PASSWORD_MIN = 8;
const PASSWORD_MAX = 72;

/** /candidate/profile — photo, personal details and password. */
export default function CandidateProfilePage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const { profile, setProfile, signIn } = useCandidateAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [detailErrors, setDetailErrors] = useState<{ fullName?: string; email?: string }>({});
  const [savingDetails, setSavingDetails] = useState(false);
  const [imageBusy, setImageBusy] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setFullName(profile.full_name);
    setEmail(profile.email);
    setPhone(profile.phone ?? "");
  }, [profile]);

  if (!profile) return <PortalLoading />;
  const image = candidateImageUrl(profile.profile_image);

  async function handleDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: typeof detailErrors = {};
    if (!fullName.trim()) errors.fullName = t("portal.profile.nameRequired");
    if (!isValidEmail(email)) errors.email = t("auth.invalidEmail");
    setDetailErrors(errors);
    if (Object.keys(errors).length) return;
    setSavingDetails(true);
    try {
      setProfile(await updateCandidateProfile({ full_name: fullName.trim(), email: email.trim(), phone: phone.trim() || null }));
      notify.success(t("portal.profile.saved"));
    } catch (error) {
      notify.error(t("portal.profile.saveFailed"), getErrorMessage(error));
    } finally {
      setSavingDetails(false);
    }
  }

  async function handleImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImageBusy(true);
    try {
      setProfile(await uploadCandidateProfileImage(file));
    } catch (error) {
      notify.error(t("portal.profile.imageFailed"), getErrorMessage(error));
    } finally {
      setImageBusy(false);
    }
  }

  async function handleRemoveImage() {
    setImageBusy(true);
    try {
      setProfile(await removeCandidateProfileImage());
    } catch (error) {
      notify.error(t("portal.profile.imageFailed"), getErrorMessage(error));
    } finally {
      setImageBusy(false);
    }
  }

  async function handlePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentPassword) return setPasswordError(t("auth.passwordRequired"));
    if (newPassword.length < PASSWORD_MIN || newPassword.length > PASSWORD_MAX) {
      return setPasswordError(t("portal.auth.passwordRule", { min: PASSWORD_MIN, max: PASSWORD_MAX }));
    }
    setPasswordError(null);
    setSavingPassword(true);
    try {
      // Other devices are signed out; this session continues with the new pair.
      signIn(await changeCandidatePassword(currentPassword, newPassword));
      setCurrentPassword("");
      setNewPassword("");
      notify.success(t("portal.profile.passwordChanged"));
    } catch (error) {
      setPasswordError(getErrorMessage(error));
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div>
      <PageMeta title={t("portal.nav.profile")} noindex />
      <section className="portal-welcome">
        <h1>{t("portal.profile.title")}</h1>
        <p>{t("portal.profile.subtitle")}</p>
      </section>

      <div className="portal-section portal-stack">
        <Card title={t("portal.profile.photo")}>
          <div className="portal-photo">
            <span className="portal-avatar" aria-hidden="true">
              {image ? <img src={image} alt="" /> : profile.full_name.slice(0, 1).toUpperCase()}
            </span>
            <div className="portal-form-actions">
              <label className="btn btn--secondary btn--sm">
                <Upload size={14} aria-hidden="true" />
                {imageBusy ? t("common.loading") : t("portal.profile.uploadPhoto")}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="visually-hidden"
                  onChange={handleImage}
                  disabled={imageBusy}
                />
              </label>
              {profile.profile_image && (
                <Button variant="ghost" size="sm" icon={<Trash2 size={14} />} onClick={handleRemoveImage} disabled={imageBusy}>
                  {t("portal.profile.removePhoto")}
                </Button>
              )}
            </div>
          </div>
          <p className="portal-muted">{t("portal.profile.photoHint")}</p>
        </Card>

        <Card title={t("portal.profile.details")}>
          <form className="portal-form" onSubmit={handleDetails} noValidate>
            <FormField label={t("portal.profile.fullName")} required error={detailErrors.fullName}>
              {(id, errorId) => (
                <input
                  id={id}
                  className={`field-input${detailErrors.fullName ? " field-input--error" : ""}`}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  aria-invalid={Boolean(detailErrors.fullName)}
                  aria-describedby={detailErrors.fullName ? errorId : undefined}
                />
              )}
            </FormField>
            <FormField label={t("auth.email")} required error={detailErrors.email}>
              {(id, errorId) => (
                <input
                  id={id}
                  type="email"
                  className={`field-input${detailErrors.email ? " field-input--error" : ""}`}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  aria-invalid={Boolean(detailErrors.email)}
                  aria-describedby={detailErrors.email ? errorId : undefined}
                />
              )}
            </FormField>
            <FormField label={t("portal.profile.phone")}>
              {(id) => (
                <input
                  id={id}
                  type="tel"
                  className="field-input"
                  value={phone}
                  maxLength={50}
                  onChange={(e) => setPhone(e.target.value)}
                  autoComplete="tel"
                />
              )}
            </FormField>
            <div className="portal-form-actions">
              <Button type="submit" loading={savingDetails}>
                {t("portal.profile.save")}
              </Button>
            </div>
          </form>
        </Card>

        {profile.has_password ? (
          <Card title={t("portal.profile.password")} subtitle={t("portal.profile.passwordHint")}>
            <form className="portal-form" onSubmit={handlePassword} noValidate>
              <PasswordInput
                label={t("portal.profile.currentPassword")}
                value={currentPassword}
                onChange={setCurrentPassword}
                autoComplete="current-password"
              />
              <PasswordInput
                label={t("portal.profile.newPassword")}
                value={newPassword}
                onChange={setNewPassword}
                autoComplete="new-password"
                error={passwordError ?? undefined}
              />
              <div className="portal-form-actions">
                <Button type="submit" loading={savingPassword}>
                  {t("portal.profile.changePassword")}
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <Card title={t("portal.profile.googleOnlyTitle")}>
            <p className="portal-muted">{t("portal.profile.googleOnlyNotice")}</p>
          </Card>
        )}
      </div>
    </div>
  );
}
