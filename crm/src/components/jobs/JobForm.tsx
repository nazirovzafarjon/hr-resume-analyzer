import { useEffect, useState } from "react";
import type { JobCreateInput } from "../../types/job";
import { useLanguage } from "../../contexts/LanguageContext";
import Button from "../ui/Button";
import BackButton from "../ui/BackButton";
import TextInput from "../forms/TextInput";
import TextArea from "../forms/TextArea";
import SkillsInput from "../forms/SkillsInput";

type JobFormProps = {
  submitLabel: string;
  initial?: JobCreateInput;
  onSubmit: (input: JobCreateInput) => void | Promise<void>;
  onDirtyChange?: (isDirty: boolean) => void;
  fallbackPath?: string;
};

type FormErrors = {
  companyName?: string;
  position?: string;
};

/**
 * Shared create/edit job form. Both pages use it so the fields, validation and
 * submit behaviour live in one place. `onSubmit` receives the ready-to-save
 * payload; the caller decides what to do next (navigate, update state).
 */
export default function JobForm({
  submitLabel,
  initial,
  onSubmit,
  onDirtyChange,
  fallbackPath,
}: JobFormProps) {
  const { t } = useLanguage();
  const [companyName, setCompanyName] = useState(initial?.company_name ?? "");
  const [position, setPosition] = useState(initial?.position ?? "");
  const [experience, setExperience] = useState(initial?.required_experience ?? "");
  const [skills, setSkills] = useState(
    initial?.required_skills
      ? initial.required_skills.split(/,\s*/).filter((skill) => skill.length > 0)
      : [],
  );
  const [description, setDescription] = useState(initial?.description ?? "");
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);

  const isDirty =
    companyName !== (initial?.company_name ?? "") ||
    position !== (initial?.position ?? "") ||
    experience !== (initial?.required_experience ?? "") ||
    skills.join(", ") !== (initial?.required_skills ?? "") ||
    description !== (initial?.description ?? "");

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  async function handleSubmit() {
    const nextErrors: FormErrors = {};
    if (!companyName.trim()) {
      nextErrors.companyName = t("jobs.companyNameRequired");
    }
    if (!position.trim()) {
      nextErrors.position = t("jobs.positionRequired");
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      await onSubmit({
        company_name: companyName.trim(),
        position: position.trim(),
        required_experience: experience.trim(),
        required_skills: skills.join(", "),
        description: description.trim(),
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="job-form">
      <TextInput
        label={t("jobs.companyName")}
        required
        value={companyName}
        onChange={(value) => {
          setCompanyName(value);
          if (errors.companyName) setErrors((prev) => ({ ...prev, companyName: undefined }));
        }}
        placeholder={t("jobs.companyNamePlaceholder")}
        error={errors.companyName}
        disabled={saving}
      />
      <TextInput
        label={t("jobs.position")}
        required
        value={position}
        onChange={(value) => {
          setPosition(value);
          if (errors.position) setErrors((prev) => ({ ...prev, position: undefined }));
        }}
        placeholder={t("jobs.positionPlaceholder")}
        error={errors.position}
        disabled={saving}
      />
      <TextInput
        label={t("jobs.requiredExperience")}
        value={experience}
        onChange={setExperience}
        placeholder={t("jobs.experiencePlaceholder")}
        hint={t("jobs.optional")}
        disabled={saving}
      />
      <SkillsInput
        label={t("jobs.skills")}
        skills={skills}
        onSkillsChange={setSkills}
        hint={t("jobs.optional")}
        disabled={saving}
      />
      <TextArea
        label={t("jobs.description")}
        value={description}
        onChange={setDescription}
        rows={4}
        placeholder={t("jobs.editDescriptionPlaceholder")}
        hint={t("jobs.optional")}
        disabled={saving}
      />

      <div className="job-form-actions">
        <BackButton
          fallbackPath={fallbackPath || ".."}
          label={t("jobs.cancel")}
          variant="secondary"
          size="md"
          isDirty={isDirty}
        />
        <Button onClick={handleSubmit} loading={saving} type="button">
          {saving ? t("jobs.saving") : submitLabel}
        </Button>
      </div>
    </div>
  );
}
