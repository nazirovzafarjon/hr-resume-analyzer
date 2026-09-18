/**
 * Options editor for select-like fields (single select / multi select).
 * HR can add, edit, delete and reorder options.
 */

import { useState } from "react";

type OptionsEditorProps = {
  options: string[];
  onChange: (options: string[]) => void;
};

export default function OptionsEditor({ options, onChange }: OptionsEditorProps) {
  const [draft, setDraft] = useState("");

  function addOption() {
    const value = draft.trim();
    if (!value) return;
    if (options.includes(value)) {
      setDraft("");
      return;
    }
    onChange([...options, value]);
    setDraft("");
  }

  function updateOption(index: number, value: string) {
    onChange(options.map((option, i) => (i === index ? value : option)));
  }

  function removeOption(index: number) {
    onChange(options.filter((_, i) => i !== index));
  }

  function moveOption(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= options.length) return;
    const next = [...options];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  return (
    <div className="options-editor">
      <p className="mini-heading">Options</p>
      {options.length === 0 && (
        <p className="muted-note">No options yet — add the choices candidates can pick.</p>
      )}
      <ul className="options-list">
        {options.map((option, index) => (
          <li key={`${option}-${index}`} className="option-row">
            <span className="option-index" aria-hidden="true">
              {index + 1}
            </span>
            <input
              className="field-input"
              value={option}
              onChange={(e) => updateOption(index, e.target.value)}
              aria-label={`Option ${index + 1}`}
            />
            <div className="option-actions">
              <button
                type="button"
                className="row-action"
                onClick={() => moveOption(index, -1)}
                disabled={index === 0}
                aria-label={`Move option ${index + 1} up`}
              >
                ↑
              </button>
              <button
                type="button"
                className="row-action"
                onClick={() => moveOption(index, 1)}
                disabled={index === options.length - 1}
                aria-label={`Move option ${index + 1} down`}
              >
                ↓
              </button>
              <button
                type="button"
                className="row-action row-action--danger"
                onClick={() => removeOption(index)}
                aria-label={`Delete option ${index + 1}`}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="option-add">
        <input
          className="field-input"
          value={draft}
          placeholder="New option…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addOption();
            }
          }}
          aria-label="New option"
        />
        <button type="button" className="row-action" onClick={addOption}>
          + Add option
        </button>
      </div>
    </div>
  );
}
