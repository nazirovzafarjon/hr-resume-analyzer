/**
 * Application-form domain types.
 *
 * These mirror the backend's `app/schemas/application_form.py`. The stored
 * data is always structured field configuration — the public form's layout
 * is rendered by the fixed `PublicApplicationFormTemplate` and is never part
 * of this data (AI model changes can never change the public UI).
 */

/** Every type the fixed public template implements (keep in sync with backend). */
export const APPLICATION_FIELD_TYPES = [
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
] as const;

export type ApplicationFieldType = (typeof APPLICATION_FIELD_TYPES)[number];

/** One question rendered on the public application form. */
export type ApplicationFieldDef = {
  id: string;
  key: string;
  label: string;
  type: ApplicationFieldType;
  required: boolean;
  description: string;
  options: string[];
  order: number;
};

/** Application form configuration owned by a job (HR view). */
export type ApplicationFormConfig = {
  job_id: number;
  public_token: string;
  fields: ApplicationFieldDef[];
  created_at: string;
  updated_at: string;
};

/**
 * HR-submitted form configuration — the `application_form` part of the job
 * create payload and the body of `PUT /jobs/{id}/application-form`
 * (mirrors the backend's `ApplicationFormPayload`).
 */
export type ApplicationFormPayload = {
  fields: ApplicationFieldDef[];
};

/** Job information shown to candidates on the public application page. */
export type PublicJobInfo = {
  company_name: string;
  position: string;
  description: string;
  required_skills: string;
  required_experience: string;
};

/** Payload of GET /api/public/applications/{token} (candidate-facing). */
export type PublicApplication = {
  job: PublicJobInfo;
  fields: ApplicationFieldDef[];
};

/** A candidate's value for one field (files are kept separately by id). */
export type ApplicationFieldValue = string | string[] | boolean | null;

/** All candidate answers keyed by field id (files handled at submit time). */
export type ApplicationValues = Record<string, ApplicationFieldValue>;

/** Per-field validation errors keyed by field id. */
export type ApplicationFieldErrors = Record<string, string>;
