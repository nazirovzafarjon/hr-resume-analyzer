"""Locate a candidate's stored CV for the protected view/download endpoint.

Resumes live in ``UPLOAD_DIR/resumes`` under server-generated names (see
``app.services.application_form.save_resume_file``). The stored
``resume_path`` is still treated as untrusted: only a relative path that
resolves to a file *inside* that directory with a whitelisted extension is
ever served, so ``..``, absolute paths, symlinks out of the folder, profile
images, ``.env`` or source files can never be reached.

Ownership (the application's job belongs to the caller) is checked by the
router before this is called.
"""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.models.worker import Worker

_RESUMES_DIR = "resumes"

#: Served content type per extension (same whitelist as uploads).
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}

NO_RESUME = "No CV is available for this application."
FILE_MISSING = "The CV file could not be found."


class ResumeUnavailableError(Exception):
    """The application has no servable CV (safe message for the client)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ResumeFile:
    path: Path
    media_type: str
    #: Friendly download name, e.g. "Jane Doe - CV.pdf" (never the stored name).
    filename: str


def _download_name(candidate_name: str, suffix: str) -> str:
    cleaned = re.sub(r"[^\w .-]+", "", candidate_name or "", flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:80]
    return f"{cleaned or 'Candidate'} - CV{suffix}"


def get_resume_file(worker: Worker) -> ResumeFile:
    """Return the CV to serve for ``worker``.

    Raises:
        ResumeUnavailableError: No CV recorded, an unsafe/unsupported stored
            path, or the file is gone from disk.
    """
    stored = (worker.resume_path or "").strip()
    if not stored or "\\" in stored or "://" in stored:
        raise ResumeUnavailableError(NO_RESUME)

    relative = PurePosixPath(stored)
    if relative.is_absolute() or ".." in relative.parts:
        raise ResumeUnavailableError(NO_RESUME)

    suffix = relative.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise ResumeUnavailableError(NO_RESUME)

    uploads_root = Path(settings.UPLOAD_DIR).resolve()
    resumes_root = uploads_root / _RESUMES_DIR
    resolved = (uploads_root / relative).resolve()  # follows symlinks
    if resumes_root not in resolved.parents:
        raise ResumeUnavailableError(NO_RESUME)
    if not resolved.is_file():
        raise ResumeUnavailableError(FILE_MISSING)

    return ResumeFile(
        path=resolved,
        media_type=media_type,
        filename=_download_name(worker.name, suffix),
    )
