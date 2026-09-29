/**
 * SortableApplicationField — one editable field card in the HR Review form
 * builder. Primary reordering UX is native HTML5 drag & drop from the visible
 * drag handle (no extra dependency); accessible fallbacks: ↑/↓ buttons and
 * ArrowUp/ArrowDown on the handle itself.
 */

import { useState } from "react";
import { GripVertical } from "lucide-react";
import type { ApplicationFieldDef, ApplicationFieldType } from "../../types/applicationForm";
import { FIELD_TYPE_ORDER, FIELD_TYPE_REGISTRY, isOptionFieldType, fieldTypeLabel } from "../../utils/fieldTypes";
import { useLanguage } from "../../contexts/LanguageContext";
import ConfirmDialog from "../ui/ConfirmDialog";
import OptionsEditor from "./OptionsEditor";

type SortableApplicationFieldProps = {
  field: ApplicationFieldDef;
  index: number;
  total: number;
  /** Reorder helper: move item at `from` to position `to`. */
  onMove: (from: number, to: number) => void;
  onChange: (field: ApplicationFieldDef) => void;
  onRemove: (id: string) => void;
  // Drag wiring owned by the builder list.
  isDragging: boolean;
  /** "before" | "after" the drop indicator line should render, or null. */
  dropPosition: "before" | "after" | null;
  onDragStart: () => void;
  onDragOverItem: () => void;
  onDropOn: () => void;
  onDragEnd: () => void;
};

export default function SortableApplicationField({
  field,
  index,
  total,
  onMove,
  onChange,
  onRemove,
  isDragging,
  dropPosition,
  onDragStart,
  onDragOverItem,
  onDropOn,
  onDragEnd,
}: SortableApplicationFieldProps) {
  const { t } = useLanguage();
  const [dragEnabled, setDragEnabled] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const classes = [
    "builder-item",
    isDragging ? "is-dragging" : "",
    dropPosition ? `is-drop-target is-drop-target--${dropPosition}` : "",
  ]
    .filter(Boolean)
    .join(" ");

  function update(patch: Partial<ApplicationFieldDef>) {
    onChange({ ...field, ...patch });
  }

  function changeType(type: ApplicationFieldType) {
    // Switching type resets options unless the new type uses them.
    const keepOptions = isOptionFieldType(type);
    update({ type, options: keepOptions ? field.options : [] });
  }

  function moveBy(direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= total) return;
    onMove(index, target);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveBy(-1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      moveBy(1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setExpanded((value) => !value);
    }
  }

  const untitled = t("applicationForm.untitledQuestion") || "Untitled question";

  return (
    <li
      className={classes}
      draggable={dragEnabled}
      onDragStart={(e) => {
        onDragStart();
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", field.id);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        onDragOverItem();
      }}
      onDrop={(e) => {
        e.preventDefault();
        onDropOn();
      }}
      onDragEnd={() => {
        setDragEnabled(false);
        onDragEnd();
      }}
    >
      <div className="builder-item-header">
        <button
          type="button"
          className="builder-handle"
          aria-label={
            t("applicationForm.reorderAriaLabel", { index: String(index + 1), label: field.label || untitled }) ||
            `Reorder field ${index + 1}: ${field.label || untitled}. Use arrow keys to move.`
          }
          title={t("applicationForm.reorderTitle") || "Drag to reorder (or use arrow keys)"}
          onPointerDown={() => setDragEnabled(true)}
          onKeyDown={handleKeyDown}
        >
          <GripVertical size={15} aria-hidden="true" />
        </button>
        <span className="builder-index" aria-hidden="true">
          {index + 1}
        </span>
        <div className="builder-summary">
          <span className="builder-label">{field.label || untitled}</span>
          <div className="form-editor-meta">
            <span className="chip">{fieldTypeLabel(field.type)}</span>
            {field.required ? (
              <span className="chip chip--danger">{t("labels.required") || "Required"}</span>
            ) : (
              <span className="chip">{t("labels.optional") || "Optional"}</span>
            )}
            {field.options.length > 0 && (
              <span className="muted-note">
                {t("applicationForm.optionsCount", { count: String(field.options.length) }) ||
                  `${field.options.length} options`}
              </span>
            )}
          </div>
        </div>
        <div className="builder-header-actions">
          <button
            type="button"
            className="row-action"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
          >
            {expanded ? t("applicationForm.done") || "Done" : t("applicationForm.edit") || "Edit"}
          </button>
          <button
            type="button"
            className="row-action row-action--danger"
            onClick={() => setConfirmingDelete(true)}
            aria-label={
              t("applicationForm.deleteFieldAriaLabel", { index: String(index + 1) }) ||
              `Delete field ${index + 1}`
            }
          >
            {t("jobs.delete") || "Delete"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="builder-edit-grid">
          <div className="builder-edit-row">
            <label>
              {t("applicationForm.label") || "Label"}
              <input
                className="field-input"
                value={field.label}
                onChange={(e) => update({ label: e.target.value })}
                placeholder="e.g. Full name"
              />
            </label>
            <label>
              {t("applicationForm.type") || "Type"}
              <select
                className="field-select"
                value={field.type}
                onChange={(e) => changeType(e.target.value as ApplicationFieldType)}
              >
                {FIELD_TYPE_ORDER.map((type) => (
                  <option key={type} value={type}>
                    {FIELD_TYPE_REGISTRY[type].label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="field-hint">{FIELD_TYPE_REGISTRY[field.type].help}</p>
          <label>
            {t("applicationForm.descriptionHelp") || "Description / help text"}
            <input
              className="field-input"
              value={field.description}
              onChange={(e) => update({ description: e.target.value })}
              placeholder={t("applicationForm.descriptionHelpPlaceholder") || "Shown under the question (optional)"}
            />
          </label>
          <label className="builder-required-toggle">
            <input
              type="checkbox"
              checked={field.required}
              onChange={(e) => update({ required: e.target.checked })}
            />
            <span>{t("applicationForm.requiredToggle") || "Required — candidates cannot submit without answering."}</span>
          </label>
          {isOptionFieldType(field.type) && (
            <OptionsEditor
              options={field.options}
              onChange={(options) => update({ options })}
            />
          )}
          <div className="builder-move-actions">
            <button
              type="button"
              className="row-action"
              onClick={() => moveBy(-1)}
              disabled={index === 0}
            >
              {t("applicationForm.moveUp") || "↑ Move up"}
            </button>
            <button
              type="button"
              className="row-action"
              onClick={() => moveBy(1)}
              disabled={index === total - 1}
            >
              {t("applicationForm.moveDown") || "↓ Move down"}
            </button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmingDelete}
        title={t("applicationForm.deleteConfirmTitle") || "Delete this field?"}
        message={
          t("applicationForm.deleteConfirmMessage") ||
          "This removes the question from the application form. This can't be undone."
        }
        confirmLabel={t("jobs.delete") || "Delete"}
        cancelLabel={t("jobs.cancel") || "Cancel"}
        onConfirm={() => {
          setConfirmingDelete(false);
          onRemove(field.id);
        }}
        onCancel={() => setConfirmingDelete(false)}
      />
    </li>
  );
}
