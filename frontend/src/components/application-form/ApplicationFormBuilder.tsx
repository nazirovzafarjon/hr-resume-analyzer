/**
 * ApplicationFormBuilder — the HR Review form builder.
 *
 * "These are the questions candidates will see." Supports editing AI-suggested
 * fields, adding custom fields (appended to the end), drag-and-drop
 * reordering with accessible ↑/↓ fallbacks, deleting fields, and managing
 * options for select-like types. Renders field *cards*, never raw JSON.
 */

import { useState } from "react";
import Button from "../ui/Button";
import EmptyState from "../ui/EmptyState";
import type { ApplicationFieldDef } from "../../types/applicationForm";
import {
  newFieldId,
  reindexFields,
  sortedFields,
  slugifyKey,
} from "../../utils/applicationFields";
import SortableApplicationField from "./SortableApplicationField";
import ApplicationFieldEditor from "./ApplicationFieldEditor";

type ApplicationFormBuilderProps = {
  fields: ApplicationFieldDef[];
  onFieldsChange: (fields: ApplicationFieldDef[]) => void;
  /** External problems (e.g. from the publish attempt) shown above the list. */
  errors?: string[] | null;
};

export default function ApplicationFormBuilder({
  fields,
  onFieldsChange,
  errors,
}: ApplicationFormBuilderProps) {
  const [editorOpen, setEditorOpen] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);

  const ordered = sortedFields(fields);

  function replaceFields(next: ApplicationFieldDef[]) {
    onFieldsChange(reindexFields(next));
  }

  /** Reorder: move item at `from` to position `to`, then reindex. */
  function moveField(from: number, to: number) {
    if (from === to || from < 0 || to < 0 || from >= ordered.length || to >= ordered.length) {
      return;
    }
    const next = [...ordered];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    replaceFields(next);
  }

  function addField(draft: ApplicationFieldDef) {
    // New fields always append to the end (spec default behaviour).
    const field: ApplicationFieldDef = {
      ...draft,
      id: newFieldId(),
      key: slugifyKey(draft.label),
    };
    replaceFields([...ordered, field]);
  }

  function clearDrag() {
    setDragIndex(null);
    setOverIndex(null);
  }

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2 className="card-title">Review application form</h2>
          <p className="card-subtitle">
            Customize the information candidates will submit. AI drafted these
            questions — you have the final say: edit, retype, reorder, add or
            delete.
          </p>
        </div>
        <div className="card-action">
          <Button onClick={() => setEditorOpen(true)}>+ Add field</Button>
        </div>
      </header>

      {errors && errors.length > 0 && (
        <div className="apply-form-error" role="alert">
          <strong>The application form needs attention:</strong>
          <ul className="bullet-list">
            {errors.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}

      {ordered.length === 0 ? (
        <EmptyState
          title="No application fields yet"
          message="Add fields manually or analyse the vacancy with AI to get suggestions."
          action={<Button onClick={() => setEditorOpen(true)}>+ Add field</Button>}
        />
      ) : (
        <ul className="builder-list">
          {ordered.map((field, index) => (
            <SortableApplicationField
              key={field.id}
              field={field}
              index={index}
              total={ordered.length}
              onMove={moveField}
              onChange={(updated) =>
                replaceFields(ordered.map((f) => (f.id === updated.id ? updated : f)))
              }
              onRemove={(id) => replaceFields(ordered.filter((f) => f.id !== id))}
              isDragging={dragIndex === index}
              isDropTarget={dragIndex !== null && overIndex === index && dragIndex !== index}
              onDragStart={() => setDragIndex(index)}
              onDragOverItem={() => setOverIndex(index)}
              onDropOn={() => {
                if (dragIndex !== null && overIndex !== null) moveField(dragIndex, overIndex);
                clearDrag();
              }}
              onDragEnd={clearDrag}
            />
          ))}
        </ul>
      )}

      <ApplicationFieldEditor
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        onAdd={addField}
      />
    </section>
  );
}
