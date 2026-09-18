/**
 * Fixed field-type registry — single source of truth for both the HR form
 * builder and the public application template.
 *
 * Only types listed here can exist in a form and be rendered; AI suggestions
 * and HR edits are constrained to this registry (mirrors the backend
 * `FIELD_TYPES` in `app/schemas/application_form.py`).
 */

import type { ApplicationFieldType } from "../types/applicationForm";

export type FieldTypeMeta = {
  /** Human label shown in the HR type picker. */
  label: string;
  /** Whether the field carries an options list (select-like). */
  hasOptions: boolean;
  /** Short help shown in the HR editor for this type. */
  help: string;
};

export const FIELD_TYPE_REGISTRY: Record<ApplicationFieldType, FieldTypeMeta> = {
  text: { label: "Text", hasOptions: false, help: "Single-line free text." },
  textarea: { label: "Long text", hasOptions: false, help: "Multi-line free text." },
  email: { label: "Email", hasOptions: false, help: "Validated email address." },
  phone: { label: "Phone", hasOptions: false, help: "Phone number input." },
  number: { label: "Number", hasOptions: false, help: "Numeric answer." },
  date: { label: "Date", hasOptions: false, help: "Date picker (YYYY-MM-DD)." },
  url: { label: "URL", hasOptions: false, help: "Validated web link." },
  select: { label: "Single select", hasOptions: true, help: "Pick one of the options." },
  multi_select: { label: "Multi select", hasOptions: true, help: "Pick several options." },
  checkbox: { label: "Checkbox", hasOptions: false, help: "Single yes/no checkbox." },
  file: {
    label: "File upload",
    hasOptions: false,
    help: "Resume upload (PDF, DOC, DOCX, TXT — max 10MB).",
  },
};

/** Stable ordering for the type picker in the HR editor. */
export const FIELD_TYPE_ORDER: ApplicationFieldType[] = [
  "text",
  "textarea",
  "email",
  "phone",
  "number",
  "date",
  "url",
  "select",
  "multi_select",
  "checkbox",
  "file",
];

export function isOptionFieldType(type: ApplicationFieldType): boolean {
  return FIELD_TYPE_REGISTRY[type].hasOptions;
}

/** Human label for a field type (safe for unknown values). */
export function fieldTypeLabel(type: string): string {
  return FIELD_TYPE_REGISTRY[type as ApplicationFieldType]?.label ?? type;
}
