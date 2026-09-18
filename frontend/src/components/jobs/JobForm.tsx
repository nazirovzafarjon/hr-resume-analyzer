import { useState } from "react";
import type { JobCreateInput } from "../../types/job";
import Button from "../ui/Button";
import TextInput from "../forms/TextInput";
import TextArea from "../forms/TextArea";
import SkillsInput from "../forms/SkillsInput";

type JobFormProps = {
  title: string;
  submitLabel: string;
  initial?: JobCreateInput;
  onSubmit: (input: JobCreateInput) => void;
};

type FormErrors = {
  companyName?: string;
  position?: string;
};

const CANCEL_TEXT = "Cancel";

/**
 * Shared create/edit job form. Both pages use it so the fields, validation and
 * submit behaviour live in one place. `onSubmit` receives the ready-to-save
 * payload; the caller decides what to do next (navigate, update state).
 */
export default function JobForm({ title, submitLabel, initial, onSubmit }: JobFormProps) {
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

  async function handleSubmit() {
    const nextErrors: FormErrors = {};
    if (!companyName.trim()) {
      nextErrors.companyName = "Company name is required.";
    }
    if (!position.trim()) {
      nextErrors.position = "Position is required.";
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    // Brief pause so the submit loading state is visible (no backend yet).
    await new Promise((resolve) => setTimeout(resolve, 420));
    onSubmit({
      company_name: companyName.trim(),
      position: position.trim(),
      required_experience: experience.trim(),
      required_skills: skills.join(", "),
      description: description.trim(),
    });
    setSaving(false);
  }

  return (
    <div className="job-form">
      <h2 className="job-form-title">{title}</h2>

      <TextInput
        label="Company name"
        required
        value={companyName}
        onChange={(value) => {
          setCompanyName(value);
          if (errors.companyName) setErrors((prev) => ({ ...prev, companyName: undefined }));
        }}
        placeholder="Acme Corp"
        error={errors.companyName}
        disabled={saving}
      />
      <TextInput
        label="Position"
        required
        value={position}
        onChange={(value) => {
          setPosition(value);
          if (errors.position) setErrors((prev) => ({ ...prev, position: undefined }));
        }}
        placeholder="Senior Python Developer"
        error={errors.position}
        disabled={saving}
      />
      <TextInput
        label="Required experience"
        value={experience}
        onChange={setExperience}
        placeholder="3+ years"
        hint="Optional"
        disabled={saving}
      />
      <SkillsInput
        label="Required skills"
        skills={skills}
        onSkillsChange={setSkills}
        hint="Optional"
        disabled={saving}
      />
      <TextArea
        label="Description"
        value={description}
        onChange={setDescription}
        rows={4}
        placeholder="Describe the role and responsibilities…"
        hint="Optional"
        disabled={saving}
      />

      <div className="job-form-actions">
        <Button to=".." variant="secondary">
          {CANCEL_TEXT}
        </Button>
        <Button onClick={handleSubmit} loading={saving} type="button">
          {saving ? "Saving…" : submitLabel}
        </Button>
      </div>
    </div>
  );
}