/**
 * ApplicationFieldEditor — modal for adding a completely custom application
 * field. Custom fields become identical to AI-suggested ones: same schema,
 * same fixed public template, no distinction on the candidate form.
 */

import { useState } from "react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import type { ApplicationFieldDef, ApplicationFieldType } from "../../types/applicationForm";
import { FIELD_TYPE_ORDER, FIELD_TYPE_REGISTRY, isOptionFieldType } from "../../utils/fieldTypes";
import OptionsEditor from "./OptionsEditor";

type ApplicationFieldEditorProps = {
  open: boolean;
  onClose: () => void;
  /** Called with the fully-typed draft when HR confirms "Add field". */
  onAdd: (draft: ApplicationFieldDef) => void;
};

export default function ApplicationFieldEditor({
  open,
  onClose,
  onAdd,
}: ApplicationFieldEditorProps) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState<ApplicationFieldType>("text");
  const [required, setRequired] = useState(false);
  const [description, setDescription] = useState("");
  const [options, setOptions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setLabel("");
    setType("text");
    setRequired(false);
    setDescription("");
    setOptions([]);
    setError(null);
  }

  function handleTypeChange(next: ApplicationFieldType) {
    setType(next);
    if (!isOptionFieldType(next)) setOptions([]);
  }

  function handleAdd() {
    if (!label.trim()) {
      setError("Enter a label for the question.");
      return;
    }
    if (isOptionFieldType(type) && options.map((o) => o.trim()).filter(Boolean).length === 0) {
      setError("Add at least one option for this field type.");
      return;
    }
    onAdd({
      id: `pending-${Date.now().toString(36)}`, // replaced by the caller
      key: "",
      label: label.trim(),
      type,
      required,
      description: description.trim(),
      options: options.map((o) => o.trim()).filter(Boolean),
      order: 0, // appended to the end by the caller
    });
    reset();
    onClose();
  }

  return (
    <Modal
      open={open}
      title="Add field"
      onClose={() => {
        reset();
        onClose();
      }}
      footer={
        <div className="job-form-actions">
          <Button
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Cancel
          </Button>
          <Button onClick={handleAdd}>+ Add field</Button>
        </div>
      }
    >
      <div className="builder-edit-grid">
        <label>
          Label
          <input
            className="field-input"
            value={label}
            onChange={(e) => {
              setLabel(e.target.value);
              if (error) setError(null);
            }}
            placeholder="e.g. Portfolio URL"
            autoFocus
          />
        </label>
        <label>
          Type
          <select
            className="field-select"
            value={type}
            onChange={(e) => handleTypeChange(e.target.value as ApplicationFieldType)}
          >
            {FIELD_TYPE_ORDER.map((optionType) => (
              <option key={optionType} value={optionType}>
                {FIELD_TYPE_REGISTRY[optionType].label}
              </option>
            ))}
          </select>
        </label>
        <p className="field-hint">{FIELD_TYPE_REGISTRY[type].help}</p>
        <label>
          Description / help text
          <input
            className="field-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Shown under the question (optional)"
          />
        </label>
        <label className="builder-required-toggle">
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
          />
          <span>Required — candidates cannot submit without answering.</span>
        </label>
        {isOptionFieldType(type) && (
          <OptionsEditor options={options} onChange={setOptions} />
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
