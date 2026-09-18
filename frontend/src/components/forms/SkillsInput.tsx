import { useState, type KeyboardEvent, type ChangeEvent } from "react";
import FormField from "./FormField";

type SkillsInputProps = {
  label: string;
  skills: string[];
  onSkillsChange: (skills: string[]) => void;
  hint?: string;
  placeholder?: string;
  disabled?: boolean;
};

/**
 * Tag-style input for required skills. Type a skill and press Enter/comma to
 * add it as a chip; remove chips with the × button. Skills are kept as an array
 * and joined into a string on save (matching the backend's `required_skills`).
 */
export default function SkillsInput({
  label,
  skills,
  onSkillsChange,
  hint,
  placeholder = "Add a skill",
  disabled = false,
}: SkillsInputProps) {
  const [draft, setDraft] = useState("");

  function addDraft() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (!skills.some((skill) => skill.toLowerCase() === trimmed.toLowerCase())) {
      onSkillsChange([...skills, trimmed]);
    }
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addDraft();
      return;
    }
    // Backspace on an empty input removes the last chip.
    if (event.key === "Backspace" && draft === "" && skills.length > 0) {
      onSkillsChange(skills.slice(0, -1));
    }
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    setDraft(event.target.value);
  }

  return (
    <FormField label={label} hint={hint}>
      {(id, _errorId) => (
        <div className="skills">
          <div className="skills-chips">
            {skills.map((skill, index) => (
              <span key={skill} className="skill-chip">
                {skill}
                <button
                  type="button"
                  className="skill-chip-remove"
                  onClick={() =>
                    onSkillsChange(skills.filter((_, i) => i !== index))
                  }
                  disabled={disabled}
                  aria-label={`Remove ${skill}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="skills-row">
            <input
              id={id}
              className="field-input"
              type="text"
              value={draft}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              onBlur={addDraft}
              placeholder={skills.length === 0 ? "Python, FastAPI, …" : placeholder}
              disabled={disabled}
            />
            <button
              type="button"
              className="btn btn--secondary"
              onClick={addDraft}
              disabled={disabled || !draft.trim()}
            >
              Add
            </button>
          </div>
          <p className="field-hint">
            {skills.length > 0
              ? `${skills.length} skill${skills.length === 1 ? "" : "s"} added.`
              : "Enter a skill and press Enter or Add."}
          </p>
        </div>
      )}
    </FormField>
  );
}