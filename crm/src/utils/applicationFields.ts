/**
 * Application-field helpers: default starter fields, client-side validation
 * (mirrors the backend's server-side rules) and multipart submission
 * building. The backend always re-validates; this exists for fast UX.
 */

import type {
  ApplicationFieldDef,
  ApplicationFieldType,
  ApplicationValues,
  ApplicationFieldErrors,
} from "../types/applicationForm";
import { FIELD_TYPE_REGISTRY, isOptionFieldType } from "./fieldTypes";
import { isValidEmail } from "./validate";

const MAX_FIELDS = 50;
/** Backend limits (app/services/application_form.py, app/schemas/application_form.py). */
export const MAX_RESUME_SIZE_MB = 10;
const MAX_RESUME_SIZE_BYTES = MAX_RESUME_SIZE_MB * 1024 * 1024;
const RESUME_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt"];
/** `accept` attribute for resume inputs (same whitelist as the backend). */
export const RESUME_ACCEPT = RESUME_EXTENSIONS.join(",");
export const MAX_TEXT_VALUE_LENGTH = 5000;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const PHONE_PATTERN = /^[+0-9()\-\s.]{6,32}$/;
const URL_PATTERN = /^https?:\/\/\S+$/i;

let uidCounter = 0;

/** Client-side unique, opaque field id (backend keeps stable ids on save). */
export function newFieldId(): string {
  uidCounter = (uidCounter + 1) % 1_000_000;
  return `fld_${Date.now().toString(36)}${uidCounter}${Math.random()
    .toString(36)
    .slice(2, 6)}`;
}

/** Machine key derived from a label ("Full Name" -> "full_name"). */
export function slugifyKey(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return slug || "field";
}

/** Create an empty editable field (append-to-end by default). */
export function createEmptyField(
  type: ApplicationFieldType = "text"
): ApplicationFieldDef {
  return {
    id: newFieldId(),
    key: "",
    label: "",
    type,
    required: false,
    description: "",
    options: [],
    order: 0,
  };
}

/**
 * Deterministic starter set used when the AI provides no usable suggestions.
 * This is *our own* default data (not AI output) — rendered by the same
 * fixed public template as everything else.
 */
export function buildDefaultApplicationFields(): ApplicationFieldDef[] {
  const raw: Array<
    Pick<ApplicationFieldDef, "label" | "type" | "required" | "description">
  > = [
    { label: "Full name", type: "text", required: true, description: "Your first and last name." },
    { label: "Email", type: "email", required: true, description: "We will contact you at this address." },
    { label: "Phone", type: "phone", required: false, description: "" },
    { label: "Resume", type: "file", required: true, description: "PDF, DOC, DOCX or TXT (max 10MB)." },
    { label: "Years of experience", type: "number", required: false, description: "" },
    { label: "Portfolio or LinkedIn URL", type: "url", required: false, description: "" },
  ];
  return raw.map((field, index) => ({
    ...field,
    id: newFieldId(),
    key: slugifyKey(field.label),
    options: [],
    order: index,
  }));
}

/** Fields sorted by their order value (the list order is authoritative). */
export function sortedFields(fields: ApplicationFieldDef[]): ApplicationFieldDef[] {
  return [...fields].sort((a, b) => a.order - b.order);
}

/**
 * Defensive conversion of AI-suggested questions into valid field definitions.
 *
 * The backend already normalises AI output against its fixed field-type
 * registry, but the candidate form must never depend on that being perfect:
 * anything unknown, blank or out of type is dropped/clamped here so only
 * structured, registry-backed fields reach the fixed public template.
 */
export function normaliseSuggestedFields(rawFields: unknown): ApplicationFieldDef[] {
  if (!Array.isArray(rawFields)) return [];
  const fields: ApplicationFieldDef[] = [];
  rawFields.slice(0, MAX_FIELDS).forEach((raw) => {
    if (!raw || typeof raw !== "object") return;
    const record = raw as Record<string, unknown>;
    const label = typeof record.label === "string" ? record.label.trim() : "";
    if (!label) return;
    const type: ApplicationFieldType =
      typeof record.type === "string" && record.type in FIELD_TYPE_REGISTRY
        ? (record.type as ApplicationFieldType)
        : "text";
    const options = Array.isArray(record.options)
      ? record.options
          .filter((option): option is string => typeof option === "string")
          .map((option) => option.trim())
          .filter(Boolean)
      : [];
    fields.push({
      id: typeof record.id === "string" && record.id ? record.id : newFieldId(),
      key:
        typeof record.key === "string" && record.key
          ? record.key
          : slugifyKey(label),
      label,
      type,
      required: record.required === true,
      description:
        typeof record.description === "string" ? record.description.trim() : "",
      options: isOptionFieldType(type) ? options : [],
      order: fields.length,
    });
  });
  return fields;
}

/**
 * The AI-drafted questions for the review step: the suggestion set when the AI
 * returned usable fields, otherwise our own deterministic starter set.
 */
export function reviewFieldsFromAnalysis(rawFields: unknown): ApplicationFieldDef[] {
  const suggested = normaliseSuggestedFields(rawFields);
  return suggested.length > 0 ? suggested : buildDefaultApplicationFields();
}

/** Reindex `order` to list position after any reorder/edit. */
export function reindexFields(fields: ApplicationFieldDef[]): ApplicationFieldDef[] {
  return fields.map((field, index) => ({ ...field, order: index }));
}

/**
 * Client-side mirror of the backend's strict publish validation.
 * Returns HR-readable problem messages (empty list = valid).
 */
export function validateApplicationFields(fields: ApplicationFieldDef[]): string[] {
  const problems: string[] = [];
  if (fields.length === 0) {
    problems.push("Add at least one application field before generating the link.");
  }
  if (fields.length > MAX_FIELDS) {
    problems.push(`A form can contain at most ${MAX_FIELDS} fields.`);
  }
  fields.forEach((field, index) => {
    const shown = field.label.trim() || `Field #${index + 1}`;
    if (!field.label.trim()) {
      problems.push(`Field #${index + 1} needs a non-empty label.`);
    }
    if (!field.type || !FIELD_TYPE_REGISTRY[field.type]) {
      problems.push(`"${shown}" has an unsupported type.`);
    }
    if (field.type && isOptionFieldType(field.type)) {
      const cleaned = field.options.map((o) => o.trim()).filter(Boolean);
      if (cleaned.length === 0) {
        problems.push(`"${shown}" needs at least one option.`);
      } else {
        if (cleaned.length !== field.options.length) {
          problems.push(`"${shown}" has empty options — remove or fill them in.`);
        }
        if (cleaned.some((o, i) => cleaned.indexOf(o) !== i)) {
          problems.push(`"${shown}" has duplicate options.`);
        }
      }
    }
  });
  return problems;
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined || value === false) return true;
  if (typeof value === "string" && !value.trim()) return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

/** Translator signature shared with `LanguageContext`'s `t`. */
type Translate = (key: string, params?: Record<string, string | number>) => string;

/**
 * Check a resume file against the backend's whitelist and size limit.
 * Returns a translated problem message, or null when the file is acceptable.
 */
export function validateResumeFile(file: File, t: Translate): string | null {
  const lower = file.name.toLowerCase();
  if (!RESUME_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
    return t("apply.errors.fileType");
  }
  if (file.size > MAX_RESUME_SIZE_BYTES) {
    return t("apply.errors.fileSize", { size: MAX_RESUME_SIZE_MB });
  }
  return null;
}

/**
 * Client-side mirror of the backend's submission validation.
 * Returns translated per-field errors (empty object = valid). File fields are
 * validated here as well because they live in the separate files record.
 */
export function validateApplicationValues(
  fields: ApplicationFieldDef[],
  values: ApplicationValues,
  files: Record<string, File | null>,
  t: Translate
): ApplicationFieldErrors {
  const errors: ApplicationFieldErrors = {};
  for (const field of sortedFields(fields)) {
    const value = values[field.id];
    const label = field.label;

    if (field.type === "file") {
      const file = files[field.id] ?? null;
      if (field.required && !file) {
        errors[field.id] = t("apply.errors.fileRequired", { label });
      } else if (file) {
        const problem = validateResumeFile(file, t);
        if (problem) errors[field.id] = problem;
      }
      continue;
    }

    if (isEmptyValue(value)) {
      if (field.required) {
        errors[field.id] =
          field.type === "checkbox"
            ? t("apply.errors.mustCheck", { label })
            : field.type === "select" || field.type === "multi_select"
              ? t("apply.errors.chooseOption", { label })
              : t("apply.errors.required", { label });
      }
      continue;
    }

    switch (field.type) {
      case "email":
        if (!isValidEmail(String(value).trim())) errors[field.id] = t("apply.errors.email");
        break;
      case "number":
        if (Number.isNaN(Number(value))) errors[field.id] = t("apply.errors.number");
        break;
      case "date":
        if (!DATE_PATTERN.test(String(value))) errors[field.id] = t("apply.errors.date");
        break;
      case "url":
        if (!URL_PATTERN.test(String(value).trim())) errors[field.id] = t("apply.errors.url");
        break;
      case "phone":
        if (!PHONE_PATTERN.test(String(value).trim())) errors[field.id] = t("apply.errors.phone");
        break;
      case "select":
        if (!field.options.includes(String(value))) errors[field.id] = t("apply.errors.option");
        break;
      case "multi_select": {
        const selected = Array.isArray(value) ? value.map(String) : [];
        if (!selected.every((option) => field.options.includes(option))) {
          errors[field.id] = t("apply.errors.option");
        }
        break;
      }
      default:
        if (String(value).length > MAX_TEXT_VALUE_LENGTH) {
          errors[field.id] = t("apply.errors.tooLong", { max: MAX_TEXT_VALUE_LENGTH });
        }
    }
  }
  return errors;
}

/** Build the multipart body: `values` JSON + one file part per file field. */
export function buildSubmissionFormData(
  fields: ApplicationFieldDef[],
  values: ApplicationValues,
  files: Record<string, File | null>
): FormData {
  const formData = new FormData();
  const plainValues: Record<string, unknown> = {};
  for (const field of fields) {
    if (field.type === "file") continue; // files travel as their own parts
    plainValues[field.id] =
      values[field.id] ?? (field.type === "multi_select" ? [] : "");
  }
  formData.append("values", JSON.stringify(plainValues));
  for (const field of sortedFields(fields)) {
    if (field.type !== "file") continue;
    const file = files[field.id];
    if (file) formData.append(field.id, file);
  }
  return formData;
}
