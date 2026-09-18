"""Pydantic schemas for the public application form feature.

This module is the *single source of truth* for the application field-type
registry. AI suggestions and HR edits both flow through the same two entry
points:

* :func:`normalize_application_fields` — lenient normalisation used for
  AI-generated suggestions and default starter fields. Invalid entries are
  dropped, never raise.
* :func:`validate_application_form_fields` — strict validation used when HR
  saves/publishes a form configuration. Raises :class:`FormValidationError`
  with an HR-friendly message.

The stored data is always a plain JSON list of field definitions; the public
form's layout/UX is rendered by the frontend's fixed template and is never
part of this data.
"""

import re
import secrets
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Fixed field-type registry (mirrored by the frontend ``utils/fieldTypes.ts``)
# ---------------------------------------------------------------------------

FieldType = Literal[
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
]

#: Every type the public template actually implements. Anything else coming
#: from an AI provider is dropped during normalisation.
FIELD_TYPES: frozenset[str] = frozenset(
    {
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
    }
)

#: Field types that carry an options list.
OPTIONAL_FIELD_TYPES: frozenset[str] = frozenset({"select", "multi_select"})

# ---------------------------------------------------------------------------
# Limits (protect the public API from oversized/malformed payloads)
# ---------------------------------------------------------------------------

MAX_FIELDS = 50
MAX_OPTIONS_PER_FIELD = 50
MAX_LABEL_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 500
MAX_OPTION_LENGTH = 200
MAX_TEXT_VALUE_LENGTH = 5000

_FIELD_ID_PREFIX = "fld_"
_FIELD_ID_BYTES = 4

_KEY_MAX_LENGTH = 64
_KEY_CLEAN_RE = re.compile(r"[^a-z0-9]+")


class FormValidationError(ValueError):
    """Raised when an HR-submitted application form configuration is invalid.

    The ``message`` is safe to show to the HR user in the UI.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def generate_field_id() -> str:
    """Return a new random, opaque field id (e.g. ``fld_1a2b3c4d``)."""
    return f"{_FIELD_ID_PREFIX}{secrets.token_hex(_FIELD_ID_BYTES)}"


def generate_public_token() -> str:
    """Return a high-entropy URL-safe public application token (~32 chars).

    Not derived from any database id, so public links cannot be enumerated.
    """
    return secrets.token_urlsafe(24)


def slugify_key(label: str, fallback: str = "field") -> str:
    """Derive a machine key (``Full Name`` -> ``full_name``) from a label."""
    slug = _KEY_CLEAN_RE.sub("_", label.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:_KEY_MAX_LENGTH] or fallback


# ---------------------------------------------------------------------------
# Field definition
# ---------------------------------------------------------------------------


class ApplicationFieldDefinition(BaseModel):
    """One question rendered on the public application form.

    ``order`` is normalised to the list index when a form is saved, so it is
    informational in payloads; the list order is authoritative.
    """

    id: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    type: FieldType
    required: bool = False
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    options: list[str] = Field(default_factory=list, max_length=MAX_OPTIONS_PER_FIELD)
    order: int = Field(default=0, ge=0)

    @field_validator("options")
    @classmethod
    def _clean_options(cls, options: list[str]) -> list[str]:
        return [option.strip() for option in options if option and option.strip()]

    @model_validator(mode="after")
    def _validate_shape(self) -> "ApplicationFieldDefinition":
        if self.type in OPTIONAL_FIELD_TYPES and not self.options:
            raise ValueError(f"Field '{self.label}' needs at least one option.")
        if self.type not in OPTIONAL_FIELD_TYPES and self.options:
            # Keep stored data clean: option lists only make sense on
            # select fields.
            self.options = []
        return self


class ApplicationFormPayload(BaseModel):
    """HR-submitted application form configuration.

    Deliberately accepts raw field dicts: all validation (labels, types,
    options) happens in ``validate_application_form_fields`` so the API can
    return one consistent, HR-friendly error message per problem instead of
    nested Pydantic error lists.
    """

    fields: list[dict[str, Any]] = Field(max_length=MAX_FIELDS)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ApplicationFormResponse(BaseModel):
    """Application form configuration returned to the owning HR user."""

    job_id: int
    public_token: str
    fields: list[ApplicationFieldDefinition]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationFormPublishRequest(BaseModel):
    """Body for the publish endpoint (optionally rotate the public token)."""

    regenerate_token: bool = False


class PublicApplicationJobInfo(BaseModel):
    """Job information safe to show to candidates on the public page."""

    company_name: str
    position: str
    description: str = ""
    required_skills: str = ""
    required_experience: str = ""


class PublicApplicationResponse(BaseModel):
    """Payload for ``GET /api/public/applications/{token}`` (candidate-facing).

    Deliberately excludes every private concern: owner id, leads count,
    internal ids, AI prompts, timestamps. Only what the fixed public
    template renders.
    """

    job: PublicApplicationJobInfo
    fields: list[ApplicationFieldDefinition]


class PublicSubmissionResult(BaseModel):
    """Minimal result returned after a successful public submission."""

    status: Literal["received"] = "received"


# ---------------------------------------------------------------------------
# Normalisation (lenient — AI suggestions / defaults) & validation (strict)
# ---------------------------------------------------------------------------


def _clean_options(raw_options: Any, label: str, strict: bool) -> list[str]:
    """Clean an options list shared by both normalisation paths."""
    if not isinstance(raw_options, list):
        if strict:
            raise FormValidationError(
                f"Field \"{label[:60]}\" has an invalid options list."
            )
        return []
    options: list[str] = []
    for option in raw_options:
        if not isinstance(option, str):
            if strict:
                raise FormValidationError(
                    f"Field \"{label[:60]}\" has an invalid option value."
                )
            continue
        option = option.strip()[:MAX_OPTION_LENGTH]
        if not option:
            if strict:
                raise FormValidationError(
                    f"Field \"{label[:60]}\" has an empty option. "
                    "Remove empty options or fill them in."
                )
            continue
        if option in options:
            if strict:
                raise FormValidationError(
                    f"Field \"{label[:60]}\" has duplicate option \"{option}\"."
                )
            continue
        options.append(option)
    return options[:MAX_OPTIONS_PER_FIELD]


def _normalise_single(raw: Any) -> ApplicationFieldDefinition | None:
    """Best-effort conversion of one raw AI-suggested field definition.

    Returns ``None`` for anything unusable (missing/blank label, unknown
    type, malformed shape). AI output never reaches the public UI unchecked.
    """
    if not isinstance(raw, dict):
        return None

    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        return None
    label = label.strip()[:MAX_LABEL_LENGTH]

    field_type = raw.get("type")
    if isinstance(field_type, str):
        field_type = field_type.strip().lower()
    if field_type not in FIELD_TYPES:
        return None

    description = raw.get("description", "")
    if not isinstance(description, str):
        description = ""

    options = _clean_options(raw.get("options") or [], label, strict=False)
    if field_type in OPTIONAL_FIELD_TYPES and not options:
        return None  # A select without options cannot render meaningfully.

    try:
        return ApplicationFieldDefinition(
            id=generate_field_id(),
            key=slugify_key(label),
            label=label,
            type=field_type,
            required=bool(raw.get("required", False)),
            description=description.strip()[:MAX_DESCRIPTION_LENGTH],
            options=options,
            order=0,
        )
    except Exception:  # noqa: BLE001 — normalisation must never raise
        return None


def _dedupe_key(
    field: ApplicationFieldDefinition, used_keys: set[str]
) -> ApplicationFieldDefinition:
    """Ensure a unique ``key`` within one form by suffixing ``_2``, ``_3``..."""
    if field.key not in used_keys:
        return field
    base_key = field.key
    suffix = 2
    candidate = field.key
    while candidate in used_keys:
        stem = base_key[: _KEY_MAX_LENGTH - len(str(suffix)) - 1]
        candidate = f"{stem}_{suffix}"
        suffix += 1
    return field.model_copy(update={"key": candidate})


def normalise_application_fields(raw_fields: Any) -> list[dict[str, Any]]:
    """Normalise raw (AI-generated or default) field definitions.

    Drops invalid entries, deduplicates keys, caps the number of fields and
    assigns fresh ids/orders. Returns plain JSON-serialisable dicts.
    """
    if not isinstance(raw_fields, list):
        return []

    normalised: list[ApplicationFieldDefinition] = []
    used_keys: set[str] = set()
    for raw in raw_fields[:MAX_FIELDS]:
        field = _normalise_single(raw)
        if field is None:
            continue
        field = _dedupe_key(field, used_keys)
        used_keys.add(field.key)
        normalised.append(field)

    return [
        field.model_copy(update={"order": index}).model_dump()
        for index, field in enumerate(normalised)
    ]


def validate_application_form_fields(raw_fields: Any) -> list[dict[str, Any]]:
    """Strictly validate an HR-submitted form configuration.

    Args:
        raw_fields: List of raw field dicts (from the HR review UI).

    Returns:
        Normalised, JSON-serialisable field list with stable ids, unique
        slug keys and sequential order values.

    Raises:
        FormValidationError: With an HR-friendly message when the form cannot
            be published (empty, blank label, unknown type, missing options).
    """
    if not isinstance(raw_fields, list):
        raise FormValidationError("Application form fields must be a list.")
    if len(raw_fields) == 0:
        raise FormValidationError(
            "Add at least one application field before generating the link."
        )
    if len(raw_fields) > MAX_FIELDS:
        raise FormValidationError(f"A form can contain at most {MAX_FIELDS} fields.")

    validated: list[ApplicationFieldDefinition] = []
    used_keys: set[str] = set()

    for index, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            raise FormValidationError(f"Field #{index + 1} has an invalid structure.")

        label = raw.get("label")
        if not isinstance(label, str) or not label.strip():
            raise FormValidationError(f"Field #{index + 1} needs a non-empty label.")
        label = label.strip()[:MAX_LABEL_LENGTH]

        field_type = raw.get("type")
        if field_type not in FIELD_TYPES:
            raise FormValidationError(
                f"Field \"{label[:60]}\" has an unsupported type. "
                "Choose one of the available field types."
            )

        description = raw.get("description", "")
        if not isinstance(description, str):
            description = ""

        options = _clean_options(raw.get("options") or [], label, strict=True)
        if field_type in OPTIONAL_FIELD_TYPES and not options:
            raise FormValidationError(
                f"Field \"{label[:60]}\" needs at least one option."
            )

        try:
            field = ApplicationFieldDefinition(
                id=str(raw.get("id") or "") or generate_field_id(),
                key=str(raw.get("key") or "") or slugify_key(label),
                label=label,
                type=field_type,
                required=bool(raw.get("required", False)),
                description=description.strip()[:MAX_DESCRIPTION_LENGTH],
                options=options,
                order=index,
            )
        except Exception:
            raise FormValidationError(  # noqa: TRY003 — translated to an HR message
                f"Field \"{label[:60]}\" has invalid data."
            ) from None

        field = _dedupe_key(field, used_keys)
        used_keys.add(field.key)
        validated.append(field)

    return [field.model_dump() for field in validated]
